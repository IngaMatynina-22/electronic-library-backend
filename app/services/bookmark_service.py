"""Bookmark management service."""

from __future__ import annotations

from app.core.database import Database
from app.core.exceptions import NotFoundError, ValidationError
from app.models.bookmark import Bookmark
from app.models.reading_location import ReadingLocation
from app.repositories.bookmark_repository import BookmarkRepository
from app.repositories.reading_repository import ReadingLocationRepository
from app.schemas.dtos import BookmarkDTO, LocationDTO
from app.schemas.mappers import to_bookmark_dto
from app.services.ownership import require_owned_book


class BookmarkService:
    def __init__(self, database: Database, auth=None) -> None:
        self.db = database
        self.auth = auth

    def _uid(self) -> int:
        return self.auth.require_user_id()

    def create(
        self,
        book_id: int,
        location: LocationDTO,
        *,
        title: str | None = None,
        note: str | None = None,
    ) -> BookmarkDTO:
        uid = self._uid()
        if not location or not location.locator:
            raise ValidationError("Bookmark requires a location")
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
            bookmark = Bookmark(
                book_id=book_id,
                location_id=db_loc.id,
                title=title,
                note=note,
            )
            BookmarkRepository(session).add(bookmark)
            bookmark = BookmarkRepository(session).get_with_location(bookmark.id)
            return to_bookmark_dto(bookmark)  # type: ignore[arg-type]

    def update(
        self,
        bookmark_id: int,
        *,
        title: str | None = ...,  # type: ignore[assignment]
        note: str | None = ...,  # type: ignore[assignment]
    ) -> BookmarkDTO:
        uid = self._uid()
        with self.db.session_scope() as session:
            repo = BookmarkRepository(session)
            bookmark = repo.get_with_location(bookmark_id)
            if bookmark is None:
                raise NotFoundError(f"Bookmark {bookmark_id} not found")
            require_owned_book(session, bookmark.book_id, uid)
            if title is not ...:
                bookmark.title = title
            if note is not ...:
                bookmark.note = note
            session.flush()
            return to_bookmark_dto(bookmark)

    def delete(self, bookmark_id: int) -> None:
        uid = self._uid()
        with self.db.session_scope() as session:
            repo = BookmarkRepository(session)
            bookmark = repo.get(bookmark_id)
            if bookmark is None:
                raise NotFoundError(f"Bookmark {bookmark_id} not found")
            require_owned_book(session, bookmark.book_id, uid)
            repo.delete(bookmark)

    def list(self, book_id: int) -> list[BookmarkDTO]:
        uid = self._uid()
        with self.db.session_scope() as session:
            require_owned_book(session, book_id, uid)
            bookmarks = BookmarkRepository(session).list_by_book(book_id)

            def sort_key(b: Bookmark) -> tuple:
                loc = b.location
                if loc and loc.page_number is not None:
                    return (0, loc.page_number, b.created_at)
                if loc and loc.position_percent is not None:
                    return (1, loc.position_percent, b.created_at)
                return (2, 0, b.created_at)

            bookmarks = sorted(bookmarks, key=sort_key)
            return [to_bookmark_dto(b) for b in bookmarks]

    def resolve_location(self, bookmark_id: int) -> LocationDTO | None:
        uid = self._uid()
        with self.db.session_scope() as session:
            bookmark = BookmarkRepository(session).get_with_location(bookmark_id)
            if bookmark is None:
                raise NotFoundError(f"Bookmark {bookmark_id} not found")
            require_owned_book(session, bookmark.book_id, uid)
            if bookmark.location is None:
                return None
            loc = bookmark.location
            return LocationDTO(
                id=loc.id,
                book_id=loc.book_id,
                location_type=loc.location_type,
                locator=loc.locator,
                page_number=loc.page_number,
                chapter_title=loc.chapter_title,
                position_percent=loc.position_percent,
            )
