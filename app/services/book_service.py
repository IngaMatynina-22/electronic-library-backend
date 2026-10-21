"""Book CRUD and metadata management."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.core.database import Database
from app.core.exceptions import ValidationError
from app.models.associations import book_authors
from app.models.book import Book
from app.models.enums import ReadingStatus
from app.repositories.author_repository import AuthorRepository, GenreRepository
from app.repositories.book_repository import BookRepository
from app.schemas.dtos import BookDTO, BookFilter, BookUpdateDTO
from app.schemas.mappers import to_book_dto
from app.services.ownership import require_owned_book, require_owned_book_relations
from app.storage.cache_manager import CacheManager
from app.storage.cover_manager import CoverManager
from app.storage.file_manager import FileManager
from app.utils.dates import ensure_naive_utc
from app.utils.validation import validate_rating, validate_status

if TYPE_CHECKING:
    from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)


class BookService:
    def __init__(
        self,
        database: Database,
        file_manager: FileManager,
        cache_manager: CacheManager,
        content_index=None,
        auth: AuthService | None = None,
        cover_manager: CoverManager | None = None,
    ) -> None:
        self.db = database
        self.files = file_manager
        self.cache = cache_manager
        self.content_index = content_index
        self.auth = auth
        self.covers = cover_manager

    def _uid(self) -> int:
        if self.auth is None:
            raise RuntimeError("AuthService is not configured")
        return self.auth.require_user_id()

    def get(self, book_id: int) -> BookDTO:
        uid = self._uid()
        with self.db.session_scope() as session:
            book = require_owned_book_relations(session, book_id, uid)
            return to_book_dto(book)

    def get_details(self, book_id: int) -> BookDTO:
        return self.get(book_id)

    def list(self, filters: BookFilter | None = None) -> list[BookDTO]:
        uid = self._uid()
        filters = filters or BookFilter()
        filters.user_id = uid
        with self.db.session_scope() as session:
            books = BookRepository(session).list_filtered(filters)
            return [to_book_dto(b) for b in books]

    def update(self, book_id: int, data: BookUpdateDTO) -> BookDTO:
        uid = self._uid()
        with self.db.session_scope() as session:
            repo = BookRepository(session)
            book = require_owned_book_relations(session, book_id, uid)

            if data.title is not None:
                title = data.title.strip()
                if not title:
                    raise ValidationError("Title is required")
                book.title = title
            if data.description is not None:
                book.description = data.description
            if data.language is not None:
                book.language = data.language
            if data.publisher is not None:
                book.publisher = data.publisher
            if data.publication_year is not None:
                book.publication_year = data.publication_year
            if data.isbn is not None:
                book.isbn = data.isbn
            if data.status is not None:
                book.status = validate_status(data.status)
            if data.rating is not None:
                book.rating = validate_rating(data.rating)
            if data.is_favorite is not None:
                book.is_favorite = data.is_favorite
            if data.is_archived is not None:
                book.is_archived = data.is_archived
            if data.author_names is not None:
                self._set_authors(session, book, data.author_names)
            if data.genre_names is not None:
                self._set_genres(session, book, data.genre_names)

            book.updated_at = ensure_naive_utc()
            session.flush()
            return to_book_dto(repo.get_with_relations(book_id))

    def set_rating(self, book_id: int, rating: int | None) -> BookDTO:
        validate_rating(rating)
        uid = self._uid()
        with self.db.session_scope() as session:
            book = require_owned_book_relations(session, book_id, uid)
            book.rating = rating
            book.updated_at = ensure_naive_utc()
            session.flush()
            return to_book_dto(book)

    def set_status(self, book_id: int, status: str) -> BookDTO:
        validate_status(status)
        uid = self._uid()
        with self.db.session_scope() as session:
            book = require_owned_book_relations(session, book_id, uid)
            book.status = status
            book.updated_at = ensure_naive_utc()
            session.flush()
            return to_book_dto(book)

    def set_cover(self, book_id: int, source_path: str | Path) -> BookDTO:
        """Replace book cover from a local image file (jpg/png/webp)."""
        if self.covers is None:
            raise ValidationError("Cover manager is not configured")
        path = Path(source_path)
        if not path.is_file():
            raise ValidationError("Cover file not found")
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}:
            raise ValidationError("Unsupported cover format. Use JPG, PNG or WEBP.")
        uid = self._uid()
        with self.db.session_scope() as session:
            require_owned_book(session, book_id, uid)
        rel = self.covers.save_cover_file(book_id, path)
        if not rel:
            raise ValidationError("Could not save cover image")
        with self.db.session_scope() as session:
            book = require_owned_book_relations(session, book_id, uid)
            book.cover_path = rel
            book.updated_at = ensure_naive_utc()
            session.flush()
            return to_book_dto(book)

    def delete(self, book_id: int, *, delete_files: bool = True) -> None:
        uid = self._uid()
        file_path = None
        cover_path = None
        with self.db.session_scope() as session:
            book = require_owned_book(session, book_id, uid)
            file_path = book.file_path
            cover_path = book.cover_path
            session.delete(book)
            session.flush()
        if self.content_index:
            try:
                self.content_index.remove_book(book_id)
            except Exception:  # noqa: BLE001
                pass
        self.cache.clear_book(book_id)
        if delete_files:
            self.files.delete_book_files(file_path, cover_path)

    def check_file_available(self, book_id: int) -> bool:
        uid = self._uid()
        with self.db.session_scope() as session:
            book = require_owned_book(session, book_id, uid)
            return self.files.is_available(book.file_path)

    @staticmethod
    def _set_authors(session: Session, book: Book, names: list[str]) -> None:
        author_repo = AuthorRepository(session)
        authors = []
        for name in names:
            if not name or not name.strip():
                continue
            authors.append(author_repo.get_or_create(name.strip()))
        book.authors = authors
        session.flush()
        for order, author in enumerate(authors):
            session.execute(
                book_authors.update()
                .where(
                    book_authors.c.book_id == book.id,
                    book_authors.c.author_id == author.id,
                )
                .values(author_order=order)
            )

    @staticmethod
    def _set_genres(session: Session, book: Book, names: list[str]) -> None:
        genre_repo = GenreRepository(session)
        genres = []
        for name in names:
            if not name or not name.strip():
                continue
            genres.append(genre_repo.get_or_create(name.strip()))
        book.genres = genres
        session.flush()

    def touch_opened(self, book_id: int) -> None:
        uid = self._uid()
        with self.db.session_scope() as session:
            book = require_owned_book(session, book_id, uid)
            book.last_opened_at = ensure_naive_utc()
            if book.status == ReadingStatus.PLANNED.value:
                book.status = ReadingStatus.READING.value
