"""Map ORM entities to DTOs."""

from __future__ import annotations

from app.models.author import Author, Genre
from app.models.bookmark import Bookmark
from app.models.book import Book
from app.models.collection import Collection
from app.models.import_job import ImportJob
from app.models.note import Note
from app.models.quote import Quote
from app.models.reading_location import ReadingLocation
from app.models.reading_progress import ReadingProgress
from app.models.reading_session import ReadingSession
from app.models.review import Review
from app.schemas.dtos import (
    AuthorDTO,
    BookmarkDTO,
    BookDTO,
    CollectionDTO,
    GenreDTO,
    ImportJobDTO,
    LocationDTO,
    NoteDTO,
    QuoteDTO,
    ReadingProgressDTO,
    ReadingSessionDTO,
    ReviewDTO,
)


def to_author_dto(author: Author) -> AuthorDTO:
    return AuthorDTO(id=author.id, name=author.name, biography=author.biography)


def to_genre_dto(genre: Genre) -> GenreDTO:
    return GenreDTO(id=genre.id, name=genre.name, description=genre.description)


def to_collection_dto(collection: Collection, book_count: int | None = None) -> CollectionDTO:
    count = book_count if book_count is not None else len(collection.books or [])
    return CollectionDTO(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        book_count=count,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


def to_location_dto(location: ReadingLocation | None) -> LocationDTO | None:
    if location is None:
        return None
    return LocationDTO(
        id=location.id,
        book_id=location.book_id,
        location_type=location.location_type,
        locator=location.locator,
        page_number=location.page_number,
        chapter_title=location.chapter_title,
        position_percent=location.position_percent,
    )


def to_progress_dto(progress: ReadingProgress | None) -> ReadingProgressDTO | None:
    if progress is None:
        return None
    return ReadingProgressDTO(
        book_id=progress.book_id,
        progress_percent=progress.progress_percent,
        current_page=progress.current_page,
        current_chapter=progress.current_chapter,
        total_units=progress.total_units,
        current_location=to_location_dto(progress.current_location),
        completed_at=progress.completed_at,
        updated_at=progress.updated_at,
    )


def to_book_dto(book: Book, *, include_relations: bool = True) -> BookDTO:
    authors = [to_author_dto(a) for a in (book.authors or [])] if include_relations else []
    genres = [to_genre_dto(g) for g in (book.genres or [])] if include_relations else []
    collections = (
        [to_collection_dto(c) for c in (book.collections or [])] if include_relations else []
    )
    progress = to_progress_dto(book.progress) if include_relations else None
    return BookDTO(
        id=book.id,
        title=book.title,
        format=book.format,
        file_path=book.file_path,
        original_filename=book.original_filename,
        file_hash=book.file_hash,
        status=book.status,
        description=book.description,
        cover_path=book.cover_path,
        language=book.language,
        publisher=book.publisher,
        publication_year=book.publication_year,
        isbn=book.isbn,
        rating=book.rating,
        is_favorite=book.is_favorite,
        is_archived=book.is_archived,
        authors=authors,
        genres=genres,
        collections=collections,
        progress=progress,
        created_at=book.created_at,
        updated_at=book.updated_at,
        last_opened_at=book.last_opened_at,
    )


def to_tag_dto(tag) -> "TagDTO":
    from app.schemas.dtos import TagDTO

    return TagDTO(id=tag.id, name=tag.name, color=tag.color)


def to_quote_dto(quote: Quote, book_title: str | None = None) -> QuoteDTO:
    tags = []
    try:
        tags = [to_tag_dto(t) for t in (quote.tags or [])]
    except Exception:
        tags = []
    return QuoteDTO(
        id=quote.id,
        book_id=quote.book_id,
        text=quote.text,
        page_number=quote.page_number,
        chapter_title=quote.chapter_title,
        note=quote.note,
        location=to_location_dto(quote.location),
        book_title=book_title or (quote.book.title if quote.book else None),
        highlight_type=getattr(quote, "highlight_type", None) or "general",
        color=getattr(quote, "color", None),
        tags=tags,
        created_at=quote.created_at,
        updated_at=quote.updated_at,
    )


def to_bookmark_dto(bookmark: Bookmark) -> BookmarkDTO:
    return BookmarkDTO(
        id=bookmark.id,
        book_id=bookmark.book_id,
        title=bookmark.title,
        note=bookmark.note,
        location=to_location_dto(bookmark.location),
        created_at=bookmark.created_at,
    )


def to_note_dto(note: Note) -> NoteDTO:
    tags = []
    related_ids: list[int] = []
    try:
        tags = [to_tag_dto(t) for t in (note.tags or [])]
    except Exception:
        tags = []
    try:
        related_ids = [n.id for n in (note.related_notes or [])]
    except Exception:
        related_ids = []
    return NoteDTO(
        id=note.id,
        book_id=note.book_id,
        content=note.content,
        title=note.title,
        location=to_location_dto(note.location),
        tags=tags,
        related_note_ids=related_ids,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


def to_review_dto(review: Review) -> ReviewDTO:
    return ReviewDTO(
        id=review.id,
        book_id=review.book_id,
        content=review.content,
        title=review.title,
        rating=review.rating,
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


def to_session_dto(session: ReadingSession) -> ReadingSessionDTO:
    return ReadingSessionDTO(
        id=session.id,
        book_id=session.book_id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        duration_seconds=session.duration_seconds,
        start_progress=session.start_progress,
        end_progress=session.end_progress,
    )


def to_import_job_dto(job: ImportJob) -> ImportJobDTO:
    return ImportJobDTO(
        id=job.id,
        source_path=job.source_path,
        status=job.status,
        file_hash=job.file_hash,
        detected_format=job.detected_format,
        error_message=job.error_message,
        book_id=job.book_id,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )
