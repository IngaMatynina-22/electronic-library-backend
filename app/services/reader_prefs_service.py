"""Reader display preferences (global + per-book), scoped per user."""

from __future__ import annotations

from sqlalchemy import select

from app.core.database import Database
from app.core.exceptions import ValidationError
from app.models.extensions import ReaderPreference
from app.schemas.dtos import ReaderPrefsDTO
from app.services.ownership import require_owned_book
from app.utils.dates import ensure_naive_utc

THEMES = {"light", "dark", "paper"}
GLOBAL_BOOK_ID = 0


class ReaderPrefsService:
    def __init__(self, database: Database, auth=None) -> None:
        self.db = database
        self.auth = auth

    def _uid(self) -> int:
        return self.auth.require_user_id()

    def get(self, book_id: int | None = None) -> ReaderPrefsDTO:
        uid = self._uid()
        with self.db.session_scope() as session:
            if book_id:
                require_owned_book(session, book_id, uid)
            global_pref = session.scalar(
                select(ReaderPreference).where(
                    ReaderPreference.user_id == uid,
                    ReaderPreference.book_id == GLOBAL_BOOK_ID,
                )
            )
            book_pref = None
            if book_id:
                book_pref = session.scalar(
                    select(ReaderPreference).where(
                        ReaderPreference.user_id == uid,
                        ReaderPreference.book_id == book_id,
                    )
                )
            base = (
                self._to_dto(global_pref)
                if global_pref
                else ReaderPrefsDTO(book_id=GLOBAL_BOOK_ID)
            )
            if book_pref is None:
                if book_id:
                    base.book_id = book_id
                return base
            merged = ReaderPrefsDTO(book_id=book_id or GLOBAL_BOOK_ID)
            for field in (
                "font_size",
                "line_spacing",
                "theme",
                "pdf_zoom",
                "pdf_mode",
                "epub_mode",
            ):
                bval = getattr(book_pref, field)
                gval = getattr(global_pref, field) if global_pref else None
                setattr(merged, field, bval if bval is not None else gval)
            return merged

    def set(
        self,
        *,
        book_id: int | None = None,
        font_size: int | None = ...,  # type: ignore[assignment]
        line_spacing: float | None = ...,  # type: ignore[assignment]
        theme: str | None = ...,  # type: ignore[assignment]
        pdf_zoom: float | None = ...,  # type: ignore[assignment]
        pdf_mode: str | None = ...,  # type: ignore[assignment]
        epub_mode: str | None = ...,  # type: ignore[assignment]
    ) -> ReaderPrefsDTO:
        uid = self._uid()
        bid = GLOBAL_BOOK_ID if book_id is None else book_id
        if bid != GLOBAL_BOOK_ID:
            with self.db.session_scope() as session:
                require_owned_book(session, bid, uid)
        if theme is not ... and theme is not None and theme not in THEMES:
            raise ValidationError(f"theme must be one of {', '.join(sorted(THEMES))}")

        with self.db.session_scope() as session:
            pref = session.scalar(
                select(ReaderPreference).where(
                    ReaderPreference.user_id == uid,
                    ReaderPreference.book_id == bid,
                )
            )
            if pref is None:
                pref = ReaderPreference(user_id=uid, book_id=bid)
                session.add(pref)
            if font_size is not ...:
                pref.font_size = font_size
            if line_spacing is not ...:
                pref.line_spacing = line_spacing
            if theme is not ...:
                pref.theme = theme
            if pdf_zoom is not ...:
                pref.pdf_zoom = pdf_zoom
            if pdf_mode is not ...:
                pref.pdf_mode = pdf_mode
            if epub_mode is not ...:
                pref.epub_mode = epub_mode
            pref.updated_at = ensure_naive_utc()
            session.flush()
            return self._to_dto(pref)

    @staticmethod
    def _to_dto(pref: ReaderPreference) -> ReaderPrefsDTO:
        return ReaderPrefsDTO(
            book_id=pref.book_id,
            font_size=pref.font_size,
            line_spacing=pref.line_spacing,
            theme=pref.theme,
            pdf_zoom=pref.pdf_zoom,
            pdf_mode=pref.pdf_mode,
            epub_mode=pref.epub_mode,
        )
