"""Tag CRUD and assignment for quotes/notes."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import Database
from app.core.exceptions import NotFoundError, ValidationError
from app.models.book import Book
from app.models.extensions import Tag
from app.models.note import Note
from app.models.quote import Quote
from app.schemas.dtos import TagDTO
from app.schemas.mappers import to_tag_dto
from app.services.ownership import require_owned_book
from app.utils.strings import normalize_name

HIGHLIGHT_TYPES = {"important", "idea", "question", "definition", "general"}


class TagService:
    def __init__(self, database: Database, auth=None) -> None:
        self.db = database
        self.auth = auth

    def _uid(self) -> int:
        return self.auth.require_user_id()

    def create(self, name: str, color: str | None = None) -> TagDTO:
        uid = self._uid()
        cleaned = (name or "").strip()
        if not cleaned:
            raise ValidationError("Tag name is required")
        with self.db.session_scope() as session:
            existing = session.scalar(
                select(Tag).where(
                    Tag.user_id == uid,
                    Tag.normalized_name == normalize_name(cleaned),
                )
            )
            if existing:
                return to_tag_dto(existing)
            tag = Tag(
                user_id=uid,
                name=cleaned,
                normalized_name=normalize_name(cleaned),
                color=color,
            )
            session.add(tag)
            session.flush()
            return to_tag_dto(tag)

    def list(self) -> list[TagDTO]:
        uid = self._uid()
        with self.db.session_scope() as session:
            tags = session.scalars(
                select(Tag).where(Tag.user_id == uid).order_by(Tag.name)
            ).all()
            return [to_tag_dto(t) for t in tags]

    def delete(self, tag_id: int) -> None:
        uid = self._uid()
        with self.db.session_scope() as session:
            tag = session.get(Tag, tag_id)
            if tag is None or tag.user_id != uid:
                raise NotFoundError(f"Tag {tag_id} not found")
            session.delete(tag)

    def get_or_create_many(self, session, names: list[str], user_id: int | None = None) -> list[Tag]:
        uid = user_id if user_id is not None else self._uid()
        result = []
        for name in names:
            if not name or not str(name).strip():
                continue
            cleaned = str(name).strip()
            tag = session.scalar(
                select(Tag).where(
                    Tag.user_id == uid,
                    Tag.normalized_name == normalize_name(cleaned),
                )
            )
            if tag is None:
                tag = Tag(
                    user_id=uid,
                    name=cleaned,
                    normalized_name=normalize_name(cleaned),
                )
                session.add(tag)
                session.flush()
            result.append(tag)
        return result

    def set_quote_tags(self, quote_id: int, tag_names: list[str]) -> list[TagDTO]:
        uid = self._uid()
        with self.db.session_scope() as session:
            quote = session.scalar(
                select(Quote).where(Quote.id == quote_id).options(selectinload(Quote.tags))
            )
            if quote is None:
                raise NotFoundError(f"Quote {quote_id} not found")
            require_owned_book(session, quote.book_id, uid)
            quote.tags = self.get_or_create_many(session, tag_names, user_id=uid)
            session.flush()
            return [to_tag_dto(t) for t in quote.tags]

    def set_note_tags(self, note_id: int, tag_names: list[str]) -> list[TagDTO]:
        uid = self._uid()
        with self.db.session_scope() as session:
            note = session.scalar(
                select(Note).where(Note.id == note_id).options(selectinload(Note.tags))
            )
            if note is None:
                raise NotFoundError(f"Note {note_id} not found")
            require_owned_book(session, note.book_id, uid)
            note.tags = self.get_or_create_many(session, tag_names, user_id=uid)
            session.flush()
            return [to_tag_dto(t) for t in note.tags]
