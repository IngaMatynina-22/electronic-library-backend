"""Collection ORM model."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.associations import book_collections
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.book import Book


class Collection(Base, TimestampMixin):
    __tablename__ = "collections"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_collection_user_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    books: Mapped[list[Book]] = relationship(
        "Book", secondary=book_collections, back_populates="collections"
    )
