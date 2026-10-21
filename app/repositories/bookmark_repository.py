"""Bookmark repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.bookmark import Bookmark
from app.repositories.base import BaseRepository


class BookmarkRepository(BaseRepository[Bookmark]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Bookmark)

    def get_with_location(self, bookmark_id: int) -> Bookmark | None:
        stmt = (
            select(Bookmark)
            .where(Bookmark.id == bookmark_id)
            .options(joinedload(Bookmark.location))
        )
        return self.session.scalars(stmt).unique().first()

    def list_by_book(self, book_id: int) -> list[Bookmark]:
        stmt = (
            select(Bookmark)
            .where(Bookmark.book_id == book_id)
            .options(joinedload(Bookmark.location))
            .order_by(Bookmark.created_at.asc())
        )
        return list(self.session.scalars(stmt).unique().all())
