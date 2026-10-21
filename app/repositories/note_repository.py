"""Note repository."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.note import Note
from app.repositories.base import BaseRepository


class NoteRepository(BaseRepository[Note]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Note)

    def get_with_location(self, note_id: int) -> Note | None:
        stmt = (
            select(Note)
            .where(Note.id == note_id)
            .options(joinedload(Note.location))
        )
        return self.session.scalars(stmt).unique().first()

    def list_by_book(self, book_id: int) -> list[Note]:
        stmt = (
            select(Note)
            .where(Note.book_id == book_id)
            .options(joinedload(Note.location))
            .order_by(Note.updated_at.desc())
        )
        return list(self.session.scalars(stmt).unique().all())

    def search(self, query: str) -> list[Note]:
        pattern = f"%{query}%"
        stmt = (
            select(Note)
            .where(or_(Note.title.ilike(pattern), Note.content.ilike(pattern)))
            .options(joinedload(Note.location))
            .order_by(Note.updated_at.desc())
        )
        return list(self.session.scalars(stmt).unique().all())
