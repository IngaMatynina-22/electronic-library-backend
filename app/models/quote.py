"""Quote ORM model."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.extensions import quote_tags

if TYPE_CHECKING:
    from app.models.book import Book
    from app.models.extensions import Tag
    from app.models.reading_location import ReadingLocation


class Quote(Base, TimestampMixin):
    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    location_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("reading_locations.id", ondelete="SET NULL"), nullable=True
    )
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chapter_title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    highlight_type: Mapped[str] = mapped_column(String(32), nullable=False, default="general")
    color: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    book: Mapped[Book] = relationship("Book", back_populates="quotes")
    location: Mapped[Optional[ReadingLocation]] = relationship("ReadingLocation")
    tags: Mapped[list[Tag]] = relationship(
        "Tag", secondary=quote_tags, back_populates="quotes"
    )
