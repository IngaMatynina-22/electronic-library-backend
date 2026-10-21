"""Book repository with filtering and sorting."""

from __future__ import annotations

from sqlalchemy import Select, and_, exists, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.associations import book_authors, book_collections, book_genres
from app.models.author import Author, Genre
from app.models.book import Book
from app.models.collection import Collection
from app.models.quote import Quote
from app.models.reading_progress import ReadingProgress
from app.models.review import Review
from app.repositories.base import BaseRepository
from app.schemas.dtos import BookFilter

SORT_FIELDS = {
    "title": Book.title,
    "created_at": Book.created_at,
    "updated_at": Book.updated_at,
    "last_opened_at": Book.last_opened_at,
    "rating": Book.rating,
    "publication_year": Book.publication_year,
    "status": Book.status,
    "progress": ReadingProgress.progress_percent,
}


class BookRepository(BaseRepository[Book]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Book)

    def get_with_relations(self, book_id: int) -> Book | None:
        stmt = (
            select(Book)
            .where(Book.id == book_id)
            .options(
                selectinload(Book.authors),
                selectinload(Book.genres),
                selectinload(Book.collections),
                joinedload(Book.progress).joinedload(ReadingProgress.current_location),
                joinedload(Book.review),
            )
        )
        return self.session.scalars(stmt).unique().first()

    def get_by_hash(self, file_hash: str, user_id: int | None = None) -> Book | None:
        stmt = select(Book).where(Book.file_hash == file_hash)
        if user_id is not None:
            stmt = stmt.where(Book.user_id == user_id)
        return self.session.scalar(stmt)

    def get_owned(self, book_id: int, user_id: int) -> Book | None:
        return self.session.scalar(
            select(Book).where(Book.id == book_id, Book.user_id == user_id)
        )

    def list_filtered(self, filters: BookFilter | None = None) -> list[Book]:
        filters = filters or BookFilter()
        stmt = select(Book).options(
            selectinload(Book.authors),
            selectinload(Book.genres),
            selectinload(Book.collections),
            joinedload(Book.progress),
        )
        stmt = self._apply_filters(stmt, filters)
        stmt = self._apply_sort(stmt, filters)
        return list(self.session.scalars(stmt).unique().all())

    def _apply_filters(self, stmt: Select, filters: BookFilter) -> Select:
        conditions = []

        if filters.user_id is not None:
            conditions.append(Book.user_id == filters.user_id)

        if filters.query:
            pattern = f"%{filters.query}%"
            author_exists = exists(
                select(1)
                .select_from(book_authors)
                .join(Author, Author.id == book_authors.c.author_id)
                .where(
                    book_authors.c.book_id == Book.id,
                    Author.name.ilike(pattern),
                )
            )
            genre_exists = exists(
                select(1)
                .select_from(book_genres)
                .join(Genre, Genre.id == book_genres.c.genre_id)
                .where(
                    book_genres.c.book_id == Book.id,
                    Genre.name.ilike(pattern),
                )
            )
            collection_exists = exists(
                select(1)
                .select_from(book_collections)
                .join(Collection, Collection.id == book_collections.c.collection_id)
                .where(
                    book_collections.c.book_id == Book.id,
                    Collection.name.ilike(pattern),
                )
            )
            quote_exists = exists(
                select(1).where(Quote.book_id == Book.id, Quote.text.ilike(pattern))
            )
            conditions.append(
                or_(
                    Book.title.ilike(pattern),
                    Book.description.ilike(pattern),
                    Book.isbn.ilike(pattern),
                    author_exists,
                    genre_exists,
                    collection_exists,
                    quote_exists,
                )
            )

        if filters.status:
            conditions.append(Book.status == filters.status)
        if filters.statuses:
            conditions.append(Book.status.in_(filters.statuses))
        if filters.format:
            conditions.append(Book.format == filters.format.upper())
        if filters.rating is not None:
            conditions.append(Book.rating == filters.rating)
        if filters.min_rating is not None:
            conditions.append(Book.rating >= filters.min_rating)
        if filters.is_favorite is not None:
            conditions.append(Book.is_favorite.is_(filters.is_favorite))
        if filters.is_archived is not None:
            conditions.append(Book.is_archived.is_(filters.is_archived))
        if filters.publication_year is not None:
            conditions.append(Book.publication_year == filters.publication_year)
        if filters.language:
            conditions.append(Book.language.ilike(filters.language))
        if filters.added_from:
            conditions.append(Book.created_at >= filters.added_from)
        if filters.added_to:
            conditions.append(Book.created_at <= filters.added_to)

        if filters.author_id is not None:
            conditions.append(
                exists(
                    select(1)
                    .select_from(book_authors)
                    .where(
                        book_authors.c.book_id == Book.id,
                        book_authors.c.author_id == filters.author_id,
                    )
                )
            )
        if filters.author_name:
            pattern = f"%{filters.author_name}%"
            conditions.append(
                exists(
                    select(1)
                    .select_from(book_authors)
                    .join(Author, Author.id == book_authors.c.author_id)
                    .where(
                        book_authors.c.book_id == Book.id,
                        Author.name.ilike(pattern),
                    )
                )
            )
        if filters.genre_ids:
            for genre_id in filters.genre_ids:
                conditions.append(
                    exists(
                        select(1)
                        .select_from(book_genres)
                        .where(
                            book_genres.c.book_id == Book.id,
                            book_genres.c.genre_id == genre_id,
                        )
                    )
                )
        if filters.genre_name:
            pattern = f"%{filters.genre_name}%"
            conditions.append(
                exists(
                    select(1)
                    .select_from(book_genres)
                    .join(Genre, Genre.id == book_genres.c.genre_id)
                    .where(
                        book_genres.c.book_id == Book.id,
                        Genre.name.ilike(pattern),
                    )
                )
            )
        if filters.collection_id is not None:
            conditions.append(
                exists(
                    select(1)
                    .select_from(book_collections)
                    .where(
                        book_collections.c.book_id == Book.id,
                        book_collections.c.collection_id == filters.collection_id,
                    )
                )
            )
        if filters.has_review is True:
            conditions.append(exists(select(1).where(Review.book_id == Book.id)))
        elif filters.has_review is False:
            conditions.append(~exists(select(1).where(Review.book_id == Book.id)))
        if filters.has_quotes is True:
            conditions.append(exists(select(1).where(Quote.book_id == Book.id)))
        elif filters.has_quotes is False:
            conditions.append(~exists(select(1).where(Quote.book_id == Book.id)))

        if conditions:
            stmt = stmt.where(and_(*conditions))
        return stmt

    def _apply_sort(self, stmt: Select, filters: BookFilter) -> Select:
        sort_key = filters.sort_by if filters.sort_by in SORT_FIELDS else "title"
        column = SORT_FIELDS[sort_key]
        if sort_key == "progress":
            stmt = stmt.outerjoin(ReadingProgress, ReadingProgress.book_id == Book.id)
        if sort_key == "title":
            # Secondary author sort support via subquery not needed for MVP.
            pass
        order = column.desc() if filters.sort_desc else column.asc()
        # Put NULLs last for rating/progress style fields
        return stmt.order_by(order.nullslast(), Book.id.asc())

    def count_by_status(self) -> dict[str, int]:
        rows = self.session.execute(
            select(Book.status, func.count(Book.id)).group_by(Book.status)
        ).all()
        return {status: count for status, count in rows}

    def count_all(self) -> int:
        return self.session.scalar(select(func.count(Book.id))) or 0
