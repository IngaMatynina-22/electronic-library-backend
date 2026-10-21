"""DTO dataclasses used between services and GUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class UserDTO:
    id: int
    username: str
    display_name: Optional[str] = None
    created_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None


@dataclass
class AuthorDTO:
    id: int
    name: str
    biography: Optional[str] = None


@dataclass
class GenreDTO:
    id: int
    name: str
    description: Optional[str] = None


@dataclass
class CollectionDTO:
    id: int
    name: str
    description: Optional[str] = None
    book_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class LocationDTO:
    id: Optional[int]
    book_id: int
    location_type: str
    locator: str
    page_number: Optional[int] = None
    chapter_title: Optional[str] = None
    position_percent: Optional[float] = None


@dataclass
class ReadingProgressDTO:
    book_id: int
    progress_percent: float
    current_page: Optional[int] = None
    current_chapter: Optional[str] = None
    total_units: Optional[int] = None
    current_location: Optional[LocationDTO] = None
    completed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class BookDTO:
    id: int
    title: str
    format: str
    file_path: str
    original_filename: str
    file_hash: str
    status: str
    description: Optional[str] = None
    cover_path: Optional[str] = None
    language: Optional[str] = None
    publisher: Optional[str] = None
    publication_year: Optional[int] = None
    isbn: Optional[str] = None
    rating: Optional[int] = None
    is_favorite: bool = False
    is_archived: bool = False
    authors: list[AuthorDTO] = field(default_factory=list)
    genres: list[GenreDTO] = field(default_factory=list)
    collections: list[CollectionDTO] = field(default_factory=list)
    progress: Optional[ReadingProgressDTO] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_opened_at: Optional[datetime] = None


@dataclass
class BookUpdateDTO:
    title: Optional[str] = None
    description: Optional[str] = None
    language: Optional[str] = None
    publisher: Optional[str] = None
    publication_year: Optional[int] = None
    isbn: Optional[str] = None
    status: Optional[str] = None
    rating: Optional[int] = None
    is_favorite: Optional[bool] = None
    is_archived: Optional[bool] = None
    author_names: Optional[list[str]] = None
    genre_names: Optional[list[str]] = None


@dataclass
class BookFilter:
    query: Optional[str] = None
    status: Optional[str] = None
    statuses: Optional[list[str]] = None
    author_id: Optional[int] = None
    author_name: Optional[str] = None
    genre_ids: Optional[list[int]] = None
    genre_name: Optional[str] = None
    rating: Optional[int] = None
    min_rating: Optional[int] = None
    is_favorite: Optional[bool] = None
    is_archived: Optional[bool] = None
    has_review: Optional[bool] = None
    has_quotes: Optional[bool] = None
    format: Optional[str] = None
    collection_id: Optional[int] = None
    publication_year: Optional[int] = None
    language: Optional[str] = None
    added_from: Optional[datetime] = None
    added_to: Optional[datetime] = None
    user_id: Optional[int] = None  # set by services from AuthService
    sort_by: str = "title"
    sort_desc: bool = False


@dataclass
class TagDTO:
    id: int
    name: str
    color: Optional[str] = None


@dataclass
class QuoteDTO:
    id: int
    book_id: int
    text: str
    page_number: Optional[int] = None
    chapter_title: Optional[str] = None
    note: Optional[str] = None
    location: Optional[LocationDTO] = None
    book_title: Optional[str] = None
    highlight_type: str = "general"
    color: Optional[str] = None
    tags: list[TagDTO] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class BookmarkDTO:
    id: int
    book_id: int
    title: Optional[str] = None
    note: Optional[str] = None
    location: Optional[LocationDTO] = None
    created_at: Optional[datetime] = None


@dataclass
class NoteDTO:
    id: int
    book_id: int
    content: str
    title: Optional[str] = None
    location: Optional[LocationDTO] = None
    tags: list[TagDTO] = field(default_factory=list)
    related_note_ids: list[int] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class ReviewDTO:
    id: int
    book_id: int
    content: str
    title: Optional[str] = None
    rating: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class ReadingSessionDTO:
    id: int
    book_id: int
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    start_progress: Optional[float] = None
    end_progress: Optional[float] = None


@dataclass
class ImportResult:
    success: bool
    status: str
    source_path: str
    book: Optional[BookDTO] = None
    book_id: Optional[int] = None
    error_message: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    job_id: Optional[int] = None
    detected_format: Optional[str] = None
    is_duplicate: bool = False


@dataclass
class ImportJobDTO:
    id: int
    source_path: str
    status: str
    file_hash: Optional[str] = None
    detected_format: Optional[str] = None
    error_message: Optional[str] = None
    book_id: Optional[int] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


@dataclass
class TocEntry:
    title: str
    location: LocationDTO
    level: int = 0
    children: list[TocEntry] = field(default_factory=list)


@dataclass
class ContentPage:
    location: LocationDTO
    content_type: str  # "text" | "html" | "image"
    content: str
    page_number: Optional[int] = None
    chapter_title: Optional[str] = None
    total_units: Optional[int] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class StatisticsDTO:
    total_books: int = 0
    completed_books: int = 0
    reading_books: int = 0
    planned_books: int = 0
    paused_books: int = 0
    abandoned_books: int = 0
    total_reading_seconds: int = 0
    average_rating: Optional[float] = None
    quotes_count: int = 0
    notes_count: int = 0
    books_by_genre: dict[str, int] = field(default_factory=dict)
    activity_by_day: dict[str, int] = field(default_factory=dict)
    activity_by_month: dict[str, int] = field(default_factory=dict)
    activity_by_year: dict[str, int] = field(default_factory=dict)
    completed_history: list[dict[str, Any]] = field(default_factory=list)
    average_active_progress: Optional[float] = None
    pages_read_estimate: int = 0
    books_completed_count: int = 0
    average_session_seconds: Optional[float] = None
    top_authors: list[dict[str, Any]] = field(default_factory=list)
    top_genres: list[dict[str, Any]] = field(default_factory=list)
    progress_history: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class BackupResult:
    success: bool
    path: Optional[str] = None
    message: str = ""
    includes_files: bool = False


@dataclass
class SearchHitDTO:
    source: str  # content | quote | note | book
    book_id: int
    book_title: Optional[str] = None
    snippet: str = ""
    locator: Optional[str] = None
    page_or_chapter: Optional[str] = None
    entity_id: Optional[int] = None


@dataclass
class ReadingGoalDTO:
    id: int
    year: int
    target_books: int
    completed_books: int = 0
    progress_percent: float = 0.0
    created_at: Optional[datetime] = None


@dataclass
class ReaderPrefsDTO:
    book_id: int = 0  # 0 = global
    font_size: Optional[int] = None
    line_spacing: Optional[float] = None
    theme: Optional[str] = None
    pdf_zoom: Optional[float] = None
    pdf_mode: Optional[str] = None
    epub_mode: Optional[str] = None


@dataclass
class OcrPageDTO:
    book_id: int
    page_number: int
    status: str
    error_message: Optional[str] = None


@dataclass
class DuplicateGroupDTO:
    key: str
    reason: str
    book_ids: list[int] = field(default_factory=list)
    titles: list[str] = field(default_factory=list)
