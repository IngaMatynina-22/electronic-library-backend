"""Current reading progress per book."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.book import Book
    from app.models.reading_location import ReadingLocation


class ReadingProgress(Base):
    __tablename__ = "reading_progress"
    __table_args__ = (UniqueConstraint("book_id", name="uq_reading_progress_book"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    current_location_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("reading_locations.id", ondelete="SET NULL"), nullable=True
    )
    progress_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    current_page: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    current_chapter: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    total_units: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    book: Mapped[Book] = relationship("Book", back_populates="progress")
    current_location: Mapped[Optional[ReadingLocation]] = relationship(
        "ReadingLocation", foreign_keys=[current_location_id]
    )
