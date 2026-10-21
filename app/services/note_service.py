"""Note management service."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from app.core.database import Database
from app.core.exceptions import NotFoundError, ValidationError
from app.models.book import Book
from app.models.note import Note
from app.models.reading_location import ReadingLocation
from app.repositories.note_repository import NoteRepository
from app.repositories.reading_repository import ReadingLocationRepository
from app.schemas.dtos import LocationDTO, NoteDTO
from app.schemas.mappers import to_note_dto
from app.services.ownership import require_owned_book
from app.services.tag_service import TagService
from app.utils.dates import ensure_naive_utc


class NoteService:
    def __init__(
        self,
        database: Database,
        content_index=None,
        tag_service: TagService | None = None,
        auth=None,
    ) -> None:
        self.db = database
        self.content_index = content_index
        self.tags = tag_service or TagService(database, auth)
        self.auth = auth

    def _uid(self) -> int:
        return self.auth.require_user_id()

    def create(
        self,
        book_id: int,
        content: str,
        *,
        title: str | None = None,
        location: LocationDTO | None = None,
        tag_names: list[str] | None = None,
        related_note_ids: list[int] | None = None,
    ) -> NoteDTO:
        uid = self._uid()
        cleaned = (content or "").strip()
        if not cleaned:
            raise ValidationError("Note content is required")
        with self.db.session_scope() as session:
            require_owned_book(session, book_id, uid)
            location_id = None
            if location is not None:
                db_loc = ReadingLocation(
                    book_id=book_id,
                    location_type=location.location_type,
                    locator=location.locator,
                    page_number=location.page_number,
                    chapter_title=location.chapter_title,
                    position_percent=location.position_percent,
                )
                ReadingLocationRepository(session).add(db_loc)
                location_id = db_loc.id
            note = Note(
                book_id=book_id,
                content=cleaned,
                title=title,
                location_id=location_id,
            )
            if tag_names:
                note.tags = self.tags.get_or_create_many(session, tag_names, user_id=uid)
            if related_note_ids:
                related = []
                for rid in related_note_ids:
                    other = session.get(Note, rid)
                    if other is not None:
                        require_owned_book(session, other.book_id, uid)
                        related.append(other)
                note.related_notes = related
            NoteRepository(session).add(note)
            nid = note.id
            note = (
                session.scalars(
                    select(Note)
                    .where(Note.id == nid)
                    .options(
                        joinedload(Note.location),
                        selectinload(Note.tags),
                        selectinload(Note.related_notes),
                    )
                )
                .unique()
                .first()
            )
            dto = to_note_dto(note)  # type: ignore[arg-type]
        if self.content_index:
            self.content_index.index_note(nid)
        return dto

    def update(
        self,
        note_id: int,
        *,
        content: str | None = None,
        title: str | None = ...,  # type: ignore[assignment]
        tag_names: list[str] | None = None,
        related_note_ids: list[int] | None = None,
    ) -> NoteDTO:
        uid = self._uid()
        with self.db.session_scope() as session:
            note = session.scalar(
                select(Note)
                .where(Note.id == note_id)
                .options(
                    joinedload(Note.location),
                    selectinload(Note.tags),
                    selectinload(Note.related_notes),
                )
            )
            if note is None:
                raise NotFoundError(f"Note {note_id} not found")
            require_owned_book(session, note.book_id, uid)
            if content is not None:
                cleaned = content.strip()
                if not cleaned:
                    raise ValidationError("Note content is required")
                note.content = cleaned
            if title is not ...:
                note.title = title
            if tag_names is not None:
                note.tags = self.tags.get_or_create_many(session, tag_names, user_id=uid)
            if related_note_ids is not None:
                related = []
                for rid in related_note_ids:
                    other = session.get(Note, rid)
                    if other is not None and other.id != note_id:
                        require_owned_book(session, other.book_id, uid)
                        related.append(other)
                note.related_notes = related
            note.updated_at = ensure_naive_utc()
            session.flush()
            dto = to_note_dto(note)
        if self.content_index:
            self.content_index.index_note(note_id)
        return dto

    def link_notes(self, note_id: int, related_note_id: int) -> NoteDTO:
        return self.update(note_id, related_note_ids=self._merged_links(note_id, related_note_id))

    def _merged_links(self, note_id: int, related_note_id: int) -> list[int]:
        uid = self._uid()
        with self.db.session_scope() as session:
            note = session.scalar(
                select(Note).where(Note.id == note_id).options(selectinload(Note.related_notes))
            )
            if note is None:
                raise NotFoundError(f"Note {note_id} not found")
            require_owned_book(session, note.book_id, uid)
            other = session.get(Note, related_note_id)
            if other is None:
                raise NotFoundError(f"Note {related_note_id} not found")
            require_owned_book(session, other.book_id, uid)
            ids = [n.id for n in note.related_notes]
            if related_note_id not in ids and related_note_id != note_id:
                ids.append(related_note_id)
            return ids

    def delete(self, note_id: int) -> None:
        uid = self._uid()
        with self.db.session_scope() as session:
            repo = NoteRepository(session)
            note = repo.get(note_id)
            if note is None:
                raise NotFoundError(f"Note {note_id} not found")
            require_owned_book(session, note.book_id, uid)
            repo.delete(note)
        if self.content_index:
            self.content_index.remove_note(note_id)

    def list(self, book_id: int | None = None) -> list[NoteDTO]:
        uid = self._uid()
        with self.db.session_scope() as session:
            if book_id is not None:
                require_owned_book(session, book_id, uid)
                notes = (
                    session.scalars(
                        select(Note)
                        .where(Note.book_id == book_id)
                        .options(
                            joinedload(Note.location),
                            selectinload(Note.tags),
                            selectinload(Note.related_notes),
                        )
                        .order_by(Note.updated_at.desc())
                    )
                    .unique()
                    .all()
                )
            else:
                notes = (
                    session.scalars(
                        select(Note)
                        .join(Book, Book.id == Note.book_id)
                        .where(Book.user_id == uid)
                        .options(
                            joinedload(Note.location),
                            selectinload(Note.tags),
                            selectinload(Note.related_notes),
                        )
                        .order_by(Note.updated_at.desc())
                    )
                    .unique()
                    .all()
                )
            return [to_note_dto(n) for n in notes]

    def search(self, query: str) -> list[NoteDTO]:
        uid = self._uid()
        with self.db.session_scope() as session:
            return [
                to_note_dto(n)
                for n in NoteRepository(session).search(query)
                if session.get(Book, n.book_id) and session.get(Book, n.book_id).user_id == uid
            ]
