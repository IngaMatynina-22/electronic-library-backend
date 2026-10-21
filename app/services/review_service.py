"""Review and rating service."""

from __future__ import annotations

from sqlalchemy import select

from app.core.database import Database
from app.core.exceptions import NotFoundError, ValidationError
from app.models.book import Book
from app.models.review import Review
from app.repositories.review_repository import ReviewRepository
from app.schemas.dtos import BookDTO, BookFilter, ReviewDTO
from app.schemas.mappers import to_book_dto, to_review_dto
from app.services.ownership import require_owned_book, require_owned_book_relations
from app.utils.dates import ensure_naive_utc
from app.utils.validation import validate_rating


class ReviewService:
    def __init__(self, database: Database, auth=None) -> None:
        self.db = database
        self.auth = auth

    def _uid(self) -> int:
        return self.auth.require_user_id()

    def create(
        self,
        book_id: int,
        content: str,
        *,
        title: str | None = None,
        rating: int | None = None,
    ) -> ReviewDTO:
        uid = self._uid()
        cleaned = (content or "").strip()
        if not cleaned:
            raise ValidationError("Review content is required")
        validate_rating(rating)
        with self.db.session_scope() as session:
            require_owned_book(session, book_id, uid)
            repo = ReviewRepository(session)
            existing = repo.get_by_book(book_id)
            if existing is not None:
                raise ValidationError("A review for this book already exists; use update instead")
            review = Review(
                book_id=book_id,
                content=cleaned,
                title=title,
                rating=rating,
            )
            repo.add(review)
            return to_review_dto(review)

    def update(
        self,
        book_id: int,
        *,
        content: str | None = None,
        title: str | None = ...,  # type: ignore[assignment]
        rating: int | None = ...,  # type: ignore[assignment]
    ) -> ReviewDTO:
        uid = self._uid()
        with self.db.session_scope() as session:
            require_owned_book(session, book_id, uid)
            repo = ReviewRepository(session)
            review = repo.get_by_book(book_id)
            if review is None:
                raise NotFoundError(f"Review for book {book_id} not found")
            if content is not None:
                cleaned = content.strip()
                if not cleaned:
                    raise ValidationError("Review content is required")
                review.content = cleaned
            if title is not ...:
                review.title = title
            if rating is not ...:
                validate_rating(rating)
                review.rating = rating
            review.updated_at = ensure_naive_utc()
            session.flush()
            return to_review_dto(review)

    def delete(self, book_id: int) -> None:
        uid = self._uid()
        with self.db.session_scope() as session:
            require_owned_book(session, book_id, uid)
            repo = ReviewRepository(session)
            review = repo.get_by_book(book_id)
            if review is None:
                raise NotFoundError(f"Review for book {book_id} not found")
            repo.delete(review)

    def get_by_book(self, book_id: int) -> ReviewDTO | None:
        uid = self._uid()
        with self.db.session_scope() as session:
            require_owned_book(session, book_id, uid)
            review = ReviewRepository(session).get_by_book(book_id)
            return to_review_dto(review) if review else None

    def list(self) -> list[ReviewDTO]:
        uid = self._uid()
        with self.db.session_scope() as session:
            reviews = session.scalars(
                select(Review)
                .join(Book, Book.id == Review.book_id)
                .where(Book.user_id == uid)
                .order_by(Review.updated_at.desc())
            ).all()
            return [to_review_dto(r) for r in reviews]

    def list_books_with_reviews(self) -> list[BookDTO]:
        uid = self._uid()
        with self.db.session_scope() as session:
            book_ids = session.scalars(
                select(Review.book_id)
                .join(Book, Book.id == Review.book_id)
                .where(Book.user_id == uid)
            ).all()
            return [
                to_book_dto(require_owned_book_relations(session, bid, uid))
                for bid in book_ids
            ]

    def list_books_without_reviews(self) -> list[BookDTO]:
        from app.repositories.book_repository import BookRepository

        uid = self._uid()
        with self.db.session_scope() as session:
            books = BookRepository(session).list_filtered(
                BookFilter(has_review=False, user_id=uid)
            )
            return [to_book_dto(b) for b in books]
