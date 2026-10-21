"""Review repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.review import Review
from app.repositories.base import BaseRepository


class ReviewRepository(BaseRepository[Review]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Review)

    def get_by_book(self, book_id: int) -> Review | None:
        return self.session.scalar(select(Review).where(Review.book_id == book_id))

    def list_all(self) -> list[Review]:
        return list(
            self.session.scalars(select(Review).order_by(Review.updated_at.desc())).all()
        )
