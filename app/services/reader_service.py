"""Embedded reader orchestration service."""

from __future__ import annotations

import logging
from pathlib import Path

from app.core.database import Database
from app.core.exceptions import FileAccessError, NotFoundError
from app.readers.base_reader import BaseReader
from app.readers.reader_factory import ReaderFactory
from app.schemas.dtos import ContentPage, LocationDTO, ReadingProgressDTO, TocEntry
from app.services.ownership import require_owned_book
from app.services.reading_service import ReadingService
from app.storage.path_resolver import PathResolver

logger = logging.getLogger(__name__)


class ReaderService:
    def __init__(
        self,
        database: Database,
        path_resolver: PathResolver,
        reading_service: ReadingService,
        auth=None,
    ) -> None:
        self.db = database
        self.paths = path_resolver
        self.reading = reading_service
        self.auth = auth
        self._open_readers: dict[int, BaseReader] = {}
        self._open_sessions: dict[int, int] = {}  # book_id -> session_id

    def _uid(self) -> int:
        return self.auth.require_user_id()

    def open_book(self, book_id: int) -> dict:
        book_path, fmt = self._resolve_book_file(book_id)
        if book_id in self._open_readers:
            self._open_readers[book_id].close()

        reader = ReaderFactory.create(book_path, fmt)
        reader.open()
        self._open_readers[book_id] = reader

        progress = self.reading.get_progress(book_id)
        start = progress.current_location or reader.make_start_location(book_id)
        session = self.reading.start_session(book_id, start)
        self._open_sessions[book_id] = session.id

        return {
            "book_id": book_id,
            "format": fmt,
            "total_units": reader.get_total_units(),
            "location": start,
            "progress": progress,
            "session_id": session.id,
        }

    def get_table_of_contents(self, book_id: int) -> list[TocEntry]:
        reader = self._ensure_open(book_id)
        return reader.get_toc(book_id)

    def get_toc(self, book_id: int) -> list[TocEntry]:
        return self.get_table_of_contents(book_id)

    def get_content(self, book_id: int, location: LocationDTO) -> ContentPage:
        reader = self._ensure_open(book_id)
        return reader.get_content(book_id, location)

    def get_next_location(self, book_id: int, location: LocationDTO) -> LocationDTO | None:
        reader = self._ensure_open(book_id)
        return reader.get_next_location(book_id, location)

    def get_previous_location(self, book_id: int, location: LocationDTO) -> LocationDTO | None:
        reader = self._ensure_open(book_id)
        return reader.get_previous_location(book_id, location)

    def get_location_context(self, book_id: int, location: LocationDTO) -> ContentPage:
        return self.get_content(book_id, location)

    def save_position(self, book_id: int, location: LocationDTO) -> ReadingProgressDTO:
        reader = self._ensure_open(book_id)
        return self.reading.update_progress(
            book_id,
            location,
            total_units=reader.get_total_units(),
        )

    def get_last_position(self, book_id: int) -> LocationDTO | None:
        progress = self.reading.get_progress(book_id)
        if progress.current_location:
            return progress.current_location
        reader = self._ensure_open(book_id)
        return reader.make_start_location(book_id)

    def close_book(self, book_id: int, location: LocationDTO | None = None) -> ReadingProgressDTO | None:
        progress = None
        if location is not None:
            try:
                reader = self._open_readers.get(book_id)
                total = reader.get_total_units() if reader else None
                progress = self.reading.update_progress(book_id, location, total_units=total)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to save position on close for book %s: %s", book_id, exc)

        session_id = self._open_sessions.pop(book_id, None)
        try:
            self.reading.finish_session(
                book_id,
                session_id=session_id,
                location=location,
                end_progress=progress.progress_percent if progress else None,
            )
        except NotFoundError:
            pass

        reader = self._open_readers.pop(book_id, None)
        if reader is not None:
            reader.close()
        return progress

    def is_open(self, book_id: int) -> bool:
        return book_id in self._open_readers

    def render_page(self, book_id: int, page_number: int, zoom: float = 1.5) -> bytes:
        """Render a PDF page to PNG bytes. Raises ValidationError for non-PDF books."""
        from app.core.exceptions import ValidationError

        reader = self._ensure_open(book_id)
        render = getattr(reader, "render_page_image", None)
        if render is None:
            raise ValidationError("Page rendering is only available for PDF books")
        return render(page_number, zoom=zoom)

    def _ensure_open(self, book_id: int) -> BaseReader:
        if book_id not in self._open_readers:
            self.open_book(book_id)
        return self._open_readers[book_id]

    def _resolve_book_file(self, book_id: int) -> tuple[Path, str]:
        uid = self._uid()
        with self.db.session_scope() as session:
            book = require_owned_book(session, book_id, uid)
            path = self.paths.resolve(book.file_path)
            fmt = book.format
        if path is None or not path.is_file():
            raise FileAccessError(
                f"Book file is missing or inaccessible for book {book_id}"
            )
        return path, fmt
