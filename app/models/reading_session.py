"""Reading session history."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.book import Book
    from app.models.reading_location import ReadingLocation


class ReadingSession(Base):
    __tablename__ = "reading_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    start_location_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("reading_locations.id", ondelete="SET NULL"), nullable=True
    )
    end_location_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("reading_locations.id", ondelete="SET NULL"), nullable=True
    )
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    start_progress: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    end_progress: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    book: Mapped[Book] = relationship("Book", back_populates="sessions")
    start_location: Mapped[Optional[ReadingLocation]] = relationship(
        "ReadingLocation", foreign_keys=[start_location_id]
    )
    end_location: Mapped[Optional[ReadingLocation]] = relationship(
        "ReadingLocation", foreign_keys=[end_location_id]
    )
