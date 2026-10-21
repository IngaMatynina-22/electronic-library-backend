"""Book import pipeline for PDF and EPUB files."""

from __future__ import annotations

import logging
import shutil
from collections.abc import Callable
from pathlib import Path

from app.core.database import Database
from app.core.exceptions import (
    CorruptedFileError,
    DuplicateBookError,
    EncryptedFileError,
    FileAccessError,
    LibraryError,
    UnsupportedFormatError,
)
from app.models.book import Book
from app.models.enums import BookFormat, ImportStatus, ReadingStatus
from app.models.import_job import ImportJob
from app.models.reading_progress import ReadingProgress
from app.readers.reader_factory import ReaderFactory
from app.repositories.author_repository import AuthorRepository, GenreRepository
from app.repositories.book_repository import BookRepository
from app.repositories.import_job_repository import ImportJobRepository
from app.schemas.dtos import ImportJobDTO, ImportResult
from app.schemas.mappers import to_book_dto, to_import_job_dto
from app.storage.cover_manager import CoverManager
from app.storage.file_manager import FileManager
from app.storage.path_resolver import PathResolver
from app.utils.dates import ensure_naive_utc

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, float], None]


class ImportService:
    def __init__(
        self,
        database: Database,
        file_manager: FileManager,
        cover_manager: CoverManager,
        path_resolver: PathResolver,
        content_index=None,
        auth=None,
    ) -> None:
        self.db = database
        self.files = file_manager
        self.covers = cover_manager
        self.paths = path_resolver
        self.content_index = content_index
        self.auth = auth

    def _uid(self) -> int:
        if self.auth is None:
            raise RuntimeError("AuthService is not configured")
        return self.auth.require_user_id()

    def check_duplicate(self, source_path: str | Path) -> int | None:
        uid = self._uid()
        path = Path(source_path)
        file_hash = self.files.compute_hash(self.files.validate_source(path))
        with self.db.session_scope() as session:
            existing = BookRepository(session).get_by_hash(file_hash, user_id=uid)
            return existing.id if existing else None

    def import_file(
        self,
        source_path: str | Path,
        *,
        author_names: list[str] | None = None,
        genre_names: list[str] | None = None,
        title_override: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> ImportResult:
        uid = self._uid()
        source = Path(source_path)
        self._notify(progress_callback, "validating", 0.05)

        job_id = self._create_job(str(source), user_id=uid)
        storage_id: str | None = None
        dest_path: Path | None = None

        try:
            validated = self.files.validate_source(source)
            self._notify(progress_callback, "hashing", 0.15)
            file_hash = self.files.compute_hash(validated)

            with self.db.session_scope() as session:
                existing = BookRepository(session).get_by_hash(file_hash, user_id=uid)
                if existing is not None:
                    self._finish_job(
                        session,
                        job_id,
                        status=ImportStatus.DUPLICATE.value,
                        file_hash=file_hash,
                        book_id=existing.id,
                        error_message=f"Duplicate of book id={existing.id}",
                        detected_format=existing.format,
                    )
                    return ImportResult(
                        success=False,
                        status=ImportStatus.DUPLICATE.value,
                        source_path=str(source),
                        book=to_book_dto(existing),
                        book_id=existing.id,
                        error_message="Book already exists in the library",
                        job_id=job_id,
                        detected_format=existing.format,
                        is_duplicate=True,
                    )

            self._update_job(job_id, status=ImportStatus.PROCESSING.value, file_hash=file_hash)
            self._notify(progress_callback, "detecting_format", 0.25)
            detected = ReaderFactory.detect_format(validated)

            self._notify(progress_callback, "extracting_metadata", 0.4)
            reader = ReaderFactory.create(validated, detected)
            reader.open()
            try:
                metadata = reader.extract_metadata()
            finally:
                reader.close()

            self._notify(progress_callback, "copying", 0.6)
            ext = "pdf" if detected == BookFormat.PDF.value else "epub"
            storage_id, dest_path = self.files.copy_to_library(validated, ext)
            relative_file = self.paths.to_relative(dest_path)

            self._notify(progress_callback, "saving", 0.8)
            with self.db.session_scope() as session:
                # Re-check duplicate inside transaction
                existing = BookRepository(session).get_by_hash(file_hash, user_id=uid)
                if existing is not None:
                    if dest_path and dest_path.exists():
                        shutil.rmtree(dest_path.parent, ignore_errors=True)
                    self._finish_job(
                        session,
                        job_id,
                        status=ImportStatus.DUPLICATE.value,
                        file_hash=file_hash,
                        book_id=existing.id,
                        detected_format=detected,
                        error_message="Duplicate detected during save",
                    )
                    return ImportResult(
                        success=False,
                        status=ImportStatus.DUPLICATE.value,
                        source_path=str(source),
                        book_id=existing.id,
                        error_message="Book already exists in the library",
                        job_id=job_id,
                        detected_format=detected,
                        is_duplicate=True,
                    )

                title = (title_override or metadata.title or validated.stem).strip()
                book = Book(
                    user_id=uid,
                    title=title,
                    description=metadata.description,
                    file_path=relative_file,
                    original_filename=validated.name,
                    format=detected,
                    file_hash=file_hash,
                    language=metadata.language,
                    publisher=metadata.publisher,
                    publication_year=metadata.publication_year,
                    isbn=metadata.isbn,
                    description_source="file_metadata" if metadata.description else None,
                    status=ReadingStatus.PLANNED.value,
                )
                session.add(book)
                session.flush()

                authors = author_names if author_names is not None else metadata.authors
                author_repo = AuthorRepository(session)
                book.authors = [author_repo.get_or_create(n) for n in authors if n and n.strip()]

                if genre_names:
                    genre_repo = GenreRepository(session)
                    book.genres = [
                        genre_repo.get_or_create(n) for n in genre_names if n and n.strip()
                    ]

                progress = ReadingProgress(
                    book_id=book.id,
                    progress_percent=0.0,
                    total_units=metadata.page_count,
                    current_page=1 if detected == BookFormat.PDF.value else None,
                )
                session.add(progress)
                session.flush()

                if metadata.cover_bytes:
                    cover_rel = self.covers.save_cover_bytes(book.id, metadata.cover_bytes)
                    book.cover_path = cover_rel

                self._finish_job(
                    session,
                    job_id,
                    status=ImportStatus.COMPLETED.value,
                    file_hash=file_hash,
                    book_id=book.id,
                    detected_format=detected,
                )
                session.flush()
                book_dto = to_book_dto(BookRepository(session).get_with_relations(book.id))

            if self.content_index and book_dto:
                try:
                    self._notify(progress_callback, "indexing", 0.95)
                    self.content_index.reindex_book(book_dto.id)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("FTS index after import failed: %s", exc)

            self._notify(progress_callback, "done", 1.0)
            return ImportResult(
                success=True,
                status=ImportStatus.COMPLETED.value,
                source_path=str(source),
                book=book_dto,
                book_id=book_dto.id if book_dto else None,
                warnings=list(metadata.warnings),
                job_id=job_id,
                detected_format=detected,
            )

        except DuplicateBookError as exc:
            self._fail_job(job_id, str(exc.message))
            return ImportResult(
                success=False,
                status=ImportStatus.DUPLICATE.value,
                source_path=str(source),
                book_id=exc.book_id,
                error_message=exc.message,
                job_id=job_id,
                is_duplicate=True,
            )
        except (UnsupportedFormatError, EncryptedFileError, CorruptedFileError, FileAccessError) as exc:
            self._cleanup_partial(dest_path)
            self._fail_job(job_id, exc.message, detected_format=None)
            return ImportResult(
                success=False,
                status=ImportStatus.FAILED.value,
                source_path=str(source),
                error_message=exc.message,
                job_id=job_id,
            )
        except LibraryError as exc:
            self._cleanup_partial(dest_path)
            self._fail_job(job_id, exc.message)
            return ImportResult(
                success=False,
                status=ImportStatus.FAILED.value,
                source_path=str(source),
                error_message=exc.message,
                job_id=job_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected import failure for %s", source)
            self._cleanup_partial(dest_path)
            message = "Unexpected error during import"
            self._fail_job(job_id, message)
            return ImportResult(
                success=False,
                status=ImportStatus.FAILED.value,
                source_path=str(source),
                error_message=message,
                job_id=job_id,
            )

    def import_files(
        self,
        source_paths: list[str | Path],
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> list[ImportResult]:
        results: list[ImportResult] = []
        total = max(1, len(source_paths))
        for index, path in enumerate(source_paths):
            def _cb(stage: str, fraction: float, i=index) -> None:
                if progress_callback:
                    overall = (i + fraction) / total
                    progress_callback(f"{Path(path).name}:{stage}", overall)

            results.append(self.import_file(path, progress_callback=_cb))
        return results

    def import_directory(
        self,
        directory: str | Path,
        *,
        recursive: bool = False,
        progress_callback: ProgressCallback | None = None,
    ) -> list[ImportResult]:
        root = Path(directory)
        if not root.is_dir():
            raise FileAccessError(f"Not a directory: {root}")
        pattern = "**/*" if recursive else "*"
        files = [
            p
            for p in root.glob(pattern)
            if p.is_file() and p.suffix.lower() in self.files.config.supported_extensions
        ]
        return self.import_files(files, progress_callback=progress_callback)

    def get_import_status(self, job_id: int) -> ImportJobDTO:
        with self.db.session_scope() as session:
            job = ImportJobRepository(session).get(job_id)
            if job is None:
                raise FileAccessError(f"Import job {job_id} not found")
            return to_import_job_dto(job)

    def list_import_jobs(self, limit: int = 50) -> list[ImportJobDTO]:
        with self.db.session_scope() as session:
            jobs = ImportJobRepository(session).list_recent(limit)
            return [to_import_job_dto(j) for j in jobs]

    def _create_job(self, source_path: str, user_id: int | None = None) -> int:
        with self.db.session_scope() as session:
            job = ImportJob(
                source_path=source_path,
                status=ImportStatus.PENDING.value,
                user_id=user_id,
            )
            session.add(job)
            session.flush()
            return job.id

    def _update_job(self, job_id: int, **fields) -> None:
        with self.db.session_scope() as session:
            job = ImportJobRepository(session).get(job_id)
            if job is None:
                return
            for key, value in fields.items():
                setattr(job, key, value)

    def _fail_job(self, job_id: int, message: str, detected_format: str | None = None) -> None:
        with self.db.session_scope() as session:
            self._finish_job(
                session,
                job_id,
                status=ImportStatus.FAILED.value,
                error_message=message,
                detected_format=detected_format,
            )

    @staticmethod
    def _finish_job(session, job_id: int, **fields) -> None:
        job = session.get(ImportJob, job_id)
        if job is None:
            return
        for key, value in fields.items():
            if value is not None or key == "error_message":
                setattr(job, key, value)
        job.finished_at = ensure_naive_utc()

    @staticmethod
    def _cleanup_partial(dest_path: Path | None) -> None:
        if dest_path and dest_path.exists():
            shutil.rmtree(dest_path.parent, ignore_errors=True)

    @staticmethod
    def _notify(callback: ProgressCallback | None, stage: str, fraction: float) -> None:
        if callback:
            callback(stage, fraction)
