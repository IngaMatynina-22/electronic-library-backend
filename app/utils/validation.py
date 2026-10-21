"""Input validation helpers."""

from __future__ import annotations

from app.core.exceptions import ValidationError
from app.models.enums import READING_STATUSES


def validate_rating(rating: int | None) -> int | None:
    if rating is None:
        return None
    if not isinstance(rating, int) or rating < 1 or rating > 5:
        raise ValidationError("Rating must be an integer from 1 to 5, or null")
    return rating


def validate_status(status: str) -> str:
    if status not in READING_STATUSES:
        raise ValidationError(
            f"Invalid reading status '{status}'. Allowed: {', '.join(sorted(READING_STATUSES))}"
        )
    return status
