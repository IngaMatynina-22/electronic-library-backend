"""Note ORM model."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.extensions import note_links, note_tags

if TYPE_CHECKING:
    from app.models.book import Book
    from app.models.extensions import Tag
    from app.models.reading_location import ReadingLocation


class Note(Base, TimestampMixin):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    location_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("reading_locations.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    book: Mapped[Book] = relationship("Book", back_populates="notes")
    location: Mapped[Optional[ReadingLocation]] = relationship("ReadingLocation")
    tags: Mapped[list[Tag]] = relationship(
        "Tag", secondary=note_tags, back_populates="notes"
    )
    related_notes: Mapped[list[Note]] = relationship(
        "Note",
        secondary=note_links,
        primaryjoin=id == note_links.c.note_id,
        secondaryjoin=id == note_links.c.related_note_id,
    )
