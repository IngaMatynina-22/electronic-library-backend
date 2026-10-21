"""Datetime helpers — store naive UTC datetimes."""

from __future__ import annotations

from datetime import datetime, timezone


def ensure_naive_utc(value: datetime | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat(sep=" ", timespec="seconds")
