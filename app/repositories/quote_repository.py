"""Quote repository."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.author import Author
from app.models.associations import book_authors
from app.models.book import Book
from app.models.quote import Quote
from app.repositories.base import BaseRepository


class QuoteRepository(BaseRepository[Quote]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Quote)

    def get_with_relations(self, quote_id: int) -> Quote | None:
        stmt = (
            select(Quote)
            .where(Quote.id == quote_id)
            .options(
                joinedload(Quote.location),
                joinedload(Quote.book),
                selectinload(Quote.tags),
            )
        )
        return self.session.scalars(stmt).unique().first()

    def list_by_book(self, book_id: int) -> list[Quote]:
        stmt = (
            select(Quote)
            .where(Quote.book_id == book_id)
            .options(
                joinedload(Quote.location),
                joinedload(Quote.book),
                selectinload(Quote.tags),
            )
            .order_by(Quote.created_at.desc())
        )
        return list(self.session.scalars(stmt).unique().all())

    def list_all(self, *, sort_by: str = "created_at", sort_desc: bool = True) -> list[Quote]:
        stmt = select(Quote).options(
            joinedload(Quote.location),
            joinedload(Quote.book),
            selectinload(Quote.tags),
        )
        if sort_by == "book_title":
            stmt = stmt.join(Book).order_by(
                Book.title.desc() if sort_desc else Book.title.asc()
            )
        else:
            stmt = stmt.order_by(
                Quote.created_at.desc() if sort_desc else Quote.created_at.asc()
            )
        return list(self.session.scalars(stmt).unique().all())

    def search(self, query: str) -> list[Quote]:
        pattern = f"%{query}%"
        author_match = (
            select(1)
            .select_from(book_authors)
            .join(Author, Author.id == book_authors.c.author_id)
            .where(
                book_authors.c.book_id == Quote.book_id,
                Author.name.ilike(pattern),
            )
            .exists()
        )
        stmt = (
            select(Quote)
            .join(Book)
            .where(
                or_(
                    Quote.text.ilike(pattern),
                    Quote.note.ilike(pattern),
                    Book.title.ilike(pattern),
                    author_match,
                )
            )
            .options(joinedload(Quote.location), joinedload(Quote.book))
            .order_by(Quote.created_at.desc())
        )
        return list(self.session.scalars(stmt).unique().all())
