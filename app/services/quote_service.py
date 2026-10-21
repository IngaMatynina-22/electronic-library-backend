"""Quote management service."""

from __future__ import annotations

from sqlalchemy.orm import selectinload

from app.core.database import Database
from app.core.exceptions import NotFoundError, ValidationError
from app.models.quote import Quote
from app.models.reading_location import ReadingLocation
from app.repositories.book_repository import BookRepository
from app.repositories.quote_repository import QuoteRepository
from app.repositories.reading_repository import ReadingLocationRepository
from app.schemas.dtos import LocationDTO, QuoteDTO
from app.schemas.mappers import to_quote_dto
from app.services.ownership import require_owned_book
from app.services.tag_service import HIGHLIGHT_TYPES, TagService
from app.utils.dates import ensure_naive_utc


class QuoteService:
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
        text: str,
        *,
        location: LocationDTO | None = None,
        page_number: int | None = None,
        chapter_title: str | None = None,
        note: str | None = None,
        highlight_type: str = "general",
        color: str | None = None,
        tag_names: list[str] | None = None,
    ) -> QuoteDTO:
        uid = self._uid()
        cleaned = (text or "").strip()
        if not cleaned:
            raise ValidationError("Quote text is required")
        ht = (highlight_type or "general").lower()
        if ht not in HIGHLIGHT_TYPES:
            raise ValidationError(f"Invalid highlight_type. Allowed: {', '.join(sorted(HIGHLIGHT_TYPES))}")
        with self.db.session_scope() as session:
            require_owned_book(session, book_id, uid)
            location_id = None
            if location is not None:
                db_loc = ReadingLocation(
                    book_id=book_id,
                    location_type=location.location_type,
                    locator=location.locator,
                    page_number=location.page_number or page_number,
                    chapter_title=location.chapter_title or chapter_title,
                    position_percent=location.position_percent,
                )
                ReadingLocationRepository(session).add(db_loc)
                location_id = db_loc.id
                page_number = page_number or location.page_number
                chapter_title = chapter_title or location.chapter_title

            quote = Quote(
                book_id=book_id,
                text=cleaned,
                location_id=location_id,
                page_number=page_number,
                chapter_title=chapter_title,
                note=note,
                highlight_type=ht,
                color=color,
            )
            if tag_names:
                quote.tags = self.tags.get_or_create_many(session, tag_names, user_id=uid)
            QuoteRepository(session).add(quote)
            qid = quote.id
            quote = QuoteRepository(session).get_with_relations(qid)
            # ensure tags loaded
            session.refresh(quote, attribute_names=["tags"])
            dto = to_quote_dto(quote)  # type: ignore[arg-type]
        if self.content_index:
            self.content_index.index_quote(qid)
        return dto

    def update(
        self,
        quote_id: int,
        *,
        text: str | None = None,
        note: str | None = ...,  # type: ignore[assignment]
        highlight_type: str | None = None,
        color: str | None = ...,  # type: ignore[assignment]
        tag_names: list[str] | None = None,
    ) -> QuoteDTO:
        uid = self._uid()
        with self.db.session_scope() as session:
            repo = QuoteRepository(session)
            quote = repo.get_with_relations(quote_id)
            if quote is None:
                raise NotFoundError(f"Quote {quote_id} not found")
            require_owned_book(session, quote.book_id, uid)
            if text is not None:
                cleaned = text.strip()
                if not cleaned:
                    raise ValidationError("Quote text is required")
                quote.text = cleaned
            if note is not ...:
                quote.note = note
            if highlight_type is not None:
                ht = highlight_type.lower()
                if ht not in HIGHLIGHT_TYPES:
                    raise ValidationError(
                        f"Invalid highlight_type. Allowed: {', '.join(sorted(HIGHLIGHT_TYPES))}"
                    )
                quote.highlight_type = ht
            if color is not ...:
                quote.color = color
            if tag_names is not None:
                quote.tags = self.tags.get_or_create_many(session, tag_names, user_id=uid)
            quote.updated_at = ensure_naive_utc()
            session.flush()
            dto = to_quote_dto(quote)
        if self.content_index:
            self.content_index.index_quote(quote_id)
        return dto

    def delete(self, quote_id: int) -> None:
        uid = self._uid()
        with self.db.session_scope() as session:
            repo = QuoteRepository(session)
            quote = repo.get(quote_id)
            if quote is None:
                raise NotFoundError(f"Quote {quote_id} not found")
            require_owned_book(session, quote.book_id, uid)
            repo.delete(quote)
        if self.content_index:
            self.content_index.remove_quote(quote_id)

    def get(self, quote_id: int) -> QuoteDTO:
        uid = self._uid()
        with self.db.session_scope() as session:
            quote = QuoteRepository(session).get_with_relations(quote_id)
            if quote is None:
                raise NotFoundError(f"Quote {quote_id} not found")
            require_owned_book(session, quote.book_id, uid)
            return to_quote_dto(quote)

    def get_by_book(self, book_id: int) -> list[QuoteDTO]:
        uid = self._uid()
        with self.db.session_scope() as session:
            require_owned_book(session, book_id, uid)
            return [to_quote_dto(q) for q in QuoteRepository(session).list_by_book(book_id)]

    def list(self, *, sort_by: str = "created_at", sort_desc: bool = True) -> list[QuoteDTO]:
        uid = self._uid()
        with self.db.session_scope() as session:
            return [
                to_quote_dto(q)
                for q in QuoteRepository(session).list_all(sort_by=sort_by, sort_desc=sort_desc)
                if q.book and q.book.user_id == uid
            ]

    def search(self, query: str) -> list[QuoteDTO]:
        uid = self._uid()
        with self.db.session_scope() as session:
            return [
                to_quote_dto(q)
                for q in QuoteRepository(session).search(query)
                if q.book and q.book.user_id == uid
            ]
