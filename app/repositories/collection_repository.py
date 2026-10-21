"""Collection repository."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.associations import book_collections
from app.models.book import Book
from app.models.collection import Collection
from app.repositories.base import BaseRepository


class CollectionRepository(BaseRepository[Collection]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Collection)

    def get_by_name(self, name: str, user_id: int | None = None) -> Collection | None:
        stmt = select(Collection).where(Collection.name == name)
        if user_id is not None:
            stmt = stmt.where(Collection.user_id == user_id)
        return self.session.scalar(stmt)

    def list_all(self, user_id: int | None = None) -> list[Collection]:
        stmt = select(Collection).options(selectinload(Collection.books)).order_by(Collection.name)
        if user_id is not None:
            stmt = stmt.where(Collection.user_id == user_id)
        return list(self.session.scalars(stmt).all())

    def add_book(self, collection: Collection, book: Book) -> None:
        if book not in collection.books:
            collection.books.append(book)
            self.session.flush()

    def remove_book(self, collection: Collection, book: Book) -> None:
        if book in collection.books:
            collection.books.remove(book)
            self.session.flush()

    def book_count(self, collection_id: int) -> int:
        return (
            self.session.scalar(
                select(func.count())
                .select_from(book_collections)
                .where(book_collections.c.collection_id == collection_id)
            )
            or 0
        )
