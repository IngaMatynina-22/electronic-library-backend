"""Book ORM model — central entity of the library."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.associations import book_authors, book_collections, book_genres
from app.models.base import Base, TimestampMixin
from app.models.enums import ReadingStatus

if TYPE_CHECKING:
    from app.models.author import Author, Genre
    from app.models.bookmark import Bookmark
    from app.models.collection import Collection
    from app.models.note import Note
    from app.models.quote import Quote
    from app.models.reading_location import ReadingLocation
    from app.models.reading_progress import ReadingProgress
    from app.models.reading_session import ReadingSession
    from app.models.review import Review
    from app.models.user import User


class Book(Base, TimestampMixin):
    __tablename__ = "books"
    __table_args__ = (UniqueConstraint("user_id", "file_hash", name="uq_book_user_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cover_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    language: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    publisher: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    publication_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    isbn: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    description_source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ReadingStatus.PLANNED.value, index=True
    )
    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    authors: Mapped[list[Author]] = relationship(
        "Author", secondary=book_authors, back_populates="books"
    )
    genres: Mapped[list[Genre]] = relationship(
        "Genre", secondary=book_genres, back_populates="books"
    )
    collections: Mapped[list[Collection]] = relationship(
        "Collection", secondary=book_collections, back_populates="books"
    )
    quotes: Mapped[list[Quote]] = relationship(
        "Quote", back_populates="book", cascade="all, delete-orphan"
    )
    bookmarks: Mapped[list[Bookmark]] = relationship(
        "Bookmark", back_populates="book", cascade="all, delete-orphan"
    )
    notes: Mapped[list[Note]] = relationship(
        "Note", back_populates="book", cascade="all, delete-orphan"
    )
    review: Mapped[Optional[Review]] = relationship(
        "Review", back_populates="book", cascade="all, delete-orphan", uselist=False
    )
    progress: Mapped[Optional[ReadingProgress]] = relationship(
        "ReadingProgress", back_populates="book", cascade="all, delete-orphan", uselist=False
    )
    sessions: Mapped[list[ReadingSession]] = relationship(
        "ReadingSession", back_populates="book", cascade="all, delete-orphan"
    )
    locations: Mapped[list[ReadingLocation]] = relationship(
        "ReadingLocation", back_populates="book", cascade="all, delete-orphan"
    )
