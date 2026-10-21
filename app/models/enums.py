"""String enums used by ORM models and services."""

from __future__ import annotations

from enum import Enum


class ReadingStatus(str, Enum):
    PLANNED = "planned"
    READING = "reading"
    COMPLETED = "completed"
    PAUSED = "paused"
    ABANDONED = "abandoned"


class BookFormat(str, Enum):
    PDF = "PDF"
    EPUB = "EPUB"


class LocationType(str, Enum):
    PDF_PAGE = "pdf_page"
    EPUB_CFI = "epub_cfi"
    EPUB_POSITION = "epub_position"


class ImportStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DUPLICATE = "duplicate"


READING_STATUSES = {s.value for s in ReadingStatus}
BOOK_FORMATS = {f.value for f in BookFormat}
