"""Declarative base and shared mixins."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, server_default=func.now(), nullable=False
    )
