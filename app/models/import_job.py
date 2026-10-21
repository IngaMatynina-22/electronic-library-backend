"""Import job journal ORM model."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow
from app.models.enums import ImportStatus


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    source_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    detected_format: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ImportStatus.PENDING.value, index=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    book_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("books.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
