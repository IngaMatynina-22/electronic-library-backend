"""Extension ORM models: tags, goals, prefs, OCR, note links."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.note import Note
    from app.models.quote import Quote

quote_tags = Table(
    "quote_tags",
    Base.metadata,
    Column("quote_id", ForeignKey("quotes.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

note_tags = Table(
    "note_tags",
    Base.metadata,
    Column("note_id", ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

note_links = Table(
    "note_links",
    Base.metadata,
    Column("note_id", ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True),
    Column("related_note_id", ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True),
)


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("user_id", "normalized_name", name="uq_tag_user_normalized"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    color: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    quotes: Mapped[list[Quote]] = relationship(
        "Quote", secondary=quote_tags, back_populates="tags"
    )
    notes: Mapped[list[Note]] = relationship(
        "Note", secondary=note_tags, back_populates="tags"
    )


class ReadingGoal(Base):
    __tablename__ = "reading_goals"
    __table_args__ = (UniqueConstraint("user_id", "year", name="uq_reading_goal_user_year"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    target_books: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class ReaderPreference(Base):
    """Global prefs use book_id = 0 (sentinel); per-book uses real book id."""

    __tablename__ = "reader_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "book_id", name="uq_reader_pref_user_book"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    font_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    line_spacing: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    theme: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    pdf_zoom: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pdf_mode: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    epub_mode: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class OcrPage(Base):
    __tablename__ = "ocr_pages"
    __table_args__ = (UniqueConstraint("book_id", "page_number", name="uq_ocr_book_page"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )
