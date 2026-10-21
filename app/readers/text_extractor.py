"""High-level text extraction helpers."""

from __future__ import annotations

from pathlib import Path

from app.readers.content_normalizer import normalize_plain_text
from app.readers.reader_factory import ReaderFactory


def extract_sample_text(file_path: Path, max_chars: int = 2000) -> str:
    """Extract a short text sample used for scanned-PDF detection."""
    reader = ReaderFactory.create(file_path)
    try:
        reader.open()
        start = reader.make_start_location(0)
        page = reader.get_content(0, start)
        return normalize_plain_text(page.content)[:max_chars]
    finally:
        reader.close()
