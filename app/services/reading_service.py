"""Reading progress and session management."""

from __future__ import annotations

from app.core.database import Database
from app.core.exceptions import NotFoundError, ValidationError
from app.models.enums import ReadingStatus
from app.models.reading_location import ReadingLocation
from app.models.reading_progress import ReadingProgress
from app.models.reading_session import ReadingSession
from app.repositories.book_repository import BookRepository
from app.repositories.reading_repository import (
    ReadingLocationRepository,
    ReadingProgressRepository,
    ReadingSessionRepository,
)
from app.schemas.dtos import LocationDTO, ReadingProgressDTO, ReadingSessionDTO
from app.schemas.mappers import to_progress_dto, to_session_dto
from app.services.ownership import require_owned_book
from app.utils.dates import ensure_naive_utc
from app.utils.progress import compute_progress_percent


class ReadingService:
    def __init__(self, database: Database, auth=None) -> None:
        self.db = database
        self.auth = auth

    def _uid(self) -> int:
        return self.auth.require_user_id()

    def get_progress(self, book_id: int) -> ReadingProgressDTO:
        uid = self._uid()
        with self.db.session_scope() as session:
            require_owned_book(session, book_id, uid)
            progress = ReadingProgressRepository(session).get_by_book(book_id)
            if progress is None:
                progress = ReadingProgress(book_id=book_id, progress_percent=0.0)
                session.add(progress)
                session.flush()
            return to_progress_dto(progress)  # type: ignore[return-value]

    def update_progress(
        self,
        book_id: int,
        location: LocationDTO,
        *,
        total_units: int | None = None,
        mark_completed: bool | None = None,
    ) -> ReadingProgressDTO:
        uid = self._uid()
        with self.db.session_scope() as session:
            book = require_owned_book(session, book_id, uid)

            loc_repo = ReadingLocationRepository(session)
            db_location = ReadingLocation(
                book_id=book_id,
                location_type=location.location_type,
                locator=location.locator,
                page_number=location.page_number,
                chapter_title=location.chapter_title,
                position_percent=location.position_percent,
            )
            loc_repo.add(db_location)

            progress_repo = ReadingProgressRepository(session)
            progress = progress_repo.get_by_book(book_id)
            if progress is None:
                progress = ReadingProgress(book_id=book_id, progress_percent=0.0)
                progress_repo.add(progress)

            if total_units is not None:
                progress.total_units = total_units

            percent = location.position_percent
            if percent is None and progress.total_units and location.page_number:
                percent = compute_progress_percent(location.page_number, progress.total_units)
            progress.progress_percent = float(percent or 0.0)
            progress.current_location_id = db_location.id
            progress.current_page = location.page_number
            progress.current_chapter = location.chapter_title
            progress.updated_at = ensure_naive_utc()

            completed = mark_completed
            if completed is None:
                completed = progress.progress_percent >= 100.0

            if completed and progress.completed_at is None:
                progress.completed_at = ensure_naive_utc()
                book.status = ReadingStatus.COMPLETED.value
            elif book.status == ReadingStatus.PLANNED.value:
                book.status = ReadingStatus.READING.value

            book.last_opened_at = ensure_naive_utc()
            session.flush()
            # Reload with location
            progress = progress_repo.get_by_book(book_id)
            return to_progress_dto(progress)  # type: ignore[return-value]

    def start_session(self, book_id: int, location: LocationDTO | None = None) -> ReadingSessionDTO:
        uid = self._uid()
        with self.db.session_scope() as session:
            book = require_owned_book(session, book_id, uid)

            session_repo = ReadingSessionRepository(session)
            active = session_repo.get_active(book_id)
            if active is not None:
                # Close orphaned session without inventing duration from now
                active.ended_at = ensure_naive_utc()
                if active.duration_seconds is None:
                    delta = (active.ended_at - active.started_at).total_seconds()
                    # Cap orphaned sessions to avoid huge crash durations; GUI should finish properly
                    active.duration_seconds = max(0, min(int(delta), 6 * 3600))

            start_location_id = None
            start_progress = None
            progress = ReadingProgressRepository(session).get_by_book(book_id)
            if progress:
                start_progress = progress.progress_percent
                start_location_id = progress.current_location_id

            if location is not None:
                db_loc = ReadingLocation(
                    book_id=book_id,
                    location_type=location.location_type,
                    locator=location.locator,
                    page_number=location.page_number,
                    chapter_title=location.chapter_title,
                    position_percent=location.position_percent,
                )
                ReadingLocationRepository(session).add(db_loc)
                start_location_id = db_loc.id
                if location.position_percent is not None:
                    start_progress = location.position_percent

            reading_session = ReadingSession(
                book_id=book_id,
                started_at=ensure_naive_utc(),
                start_location_id=start_location_id,
                start_progress=start_progress,
            )
            session_repo.add(reading_session)

            if book.status == ReadingStatus.PLANNED.value:
                book.status = ReadingStatus.READING.value
            book.last_opened_at = ensure_naive_utc()
            session.flush()
            return to_session_dto(reading_session)

    def finish_session(
        self,
        book_id: int,
        *,
        session_id: int | None = None,
        location: LocationDTO | None = None,
        end_progress: float | None = None,
    ) -> ReadingSessionDTO:
        uid = self._uid()
        with self.db.session_scope() as session:
            require_owned_book(session, book_id, uid)
            session_repo = ReadingSessionRepository(session)
            if session_id is not None:
                reading_session = session_repo.get(session_id)
            else:
                reading_session = session_repo.get_active(book_id)
            if reading_session is None or reading_session.book_id != book_id:
                raise NotFoundError("Active reading session not found")
            if reading_session.ended_at is not None:
                return to_session_dto(reading_session)

            end_location_id = None
            if location is not None:
                db_loc = ReadingLocation(
                    book_id=book_id,
                    location_type=location.location_type,
                    locator=location.locator,
                    page_number=location.page_number,
                    chapter_title=location.chapter_title,
                    position_percent=location.position_percent,
                )
                ReadingLocationRepository(session).add(db_loc)
                end_location_id = db_loc.id
                if end_progress is None:
                    end_progress = location.position_percent

            now = ensure_naive_utc()
            reading_session.ended_at = now
            reading_session.end_location_id = end_location_id
            reading_session.end_progress = end_progress
            reading_session.duration_seconds = max(
                0, int((now - reading_session.started_at).total_seconds())
            )
            session.flush()
            return to_session_dto(reading_session)

    def get_history(self, book_id: int | None = None) -> list[ReadingSessionDTO]:
        uid = self._uid()
        with self.db.session_scope() as session:
            repo = ReadingSessionRepository(session)
            if book_id is not None:
                require_owned_book(session, book_id, uid)
                sessions = repo.list_by_book(book_id)
            else:
                from app.models.book import Book
                from sqlalchemy import select

                sessions = list(
                    session.scalars(
                        select(ReadingSession)
                        .join(Book, Book.id == ReadingSession.book_id)
                        .where(Book.user_id == uid)
                        .order_by(ReadingSession.started_at.desc())
                    ).all()
                )
            return [to_session_dto(s) for s in sessions]

    def create_location(self, book_id: int, location: LocationDTO) -> LocationDTO:
        uid = self._uid()
        if not location.locator:
            raise ValidationError("Location locator is required")
        with self.db.session_scope() as session:
            require_owned_book(session, book_id, uid)
            db_loc = ReadingLocation(
                book_id=book_id,
                location_type=location.location_type,
                locator=location.locator,
                page_number=location.page_number,
                chapter_title=location.chapter_title,
                position_percent=location.position_percent,
            )
            ReadingLocationRepository(session).add(db_loc)
            return LocationDTO(
                id=db_loc.id,
                book_id=db_loc.book_id,
                location_type=db_loc.location_type,
                locator=db_loc.locator,
                page_number=db_loc.page_number,
                chapter_title=db_loc.chapter_title,
                position_percent=db_loc.position_percent,
            )
