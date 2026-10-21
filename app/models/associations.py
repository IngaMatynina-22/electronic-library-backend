"""Association tables for many-to-many relationships."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Table, UniqueConstraint

from app.models.base import Base, utcnow

book_authors = Table(
    "book_authors",
    Base.metadata,
    Column("book_id", ForeignKey("books.id", ondelete="CASCADE"), primary_key=True),
    Column("author_id", ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True),
    Column("author_order", Integer, nullable=False, default=0),
)

book_genres = Table(
    "book_genres",
    Base.metadata,
    Column("book_id", ForeignKey("books.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True),
)

book_collections = Table(
    "book_collections",
    Base.metadata,
    Column("book_id", ForeignKey("books.id", ondelete="CASCADE"), primary_key=True),
    Column("collection_id", ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True),
    Column("added_at", DateTime, nullable=False, default=utcnow),
    UniqueConstraint("book_id", "collection_id", name="uq_book_collection"),
)
