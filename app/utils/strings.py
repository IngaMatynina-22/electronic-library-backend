"""String normalization helpers."""

from __future__ import annotations

import re
import unicodedata


def normalize_name(value: str) -> str:
    """Normalize author/genre names for deduplication."""
    text = unicodedata.normalize("NFKC", value or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_search(value: str) -> str:
    """Normalize free-text search input."""
    return re.sub(r"\s+", " ", (value or "").strip())
