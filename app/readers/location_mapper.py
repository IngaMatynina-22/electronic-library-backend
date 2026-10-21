"""Helpers to build and interpret reading locations."""

from __future__ import annotations

from app.models.enums import LocationType
from app.schemas.dtos import LocationDTO
from app.utils.progress import compute_progress_percent


def pdf_location(
    book_id: int,
    page_number: int,
    total_pages: int,
    *,
    location_id: int | None = None,
) -> LocationDTO:
    percent = compute_progress_percent(page_number, total_pages)
    return LocationDTO(
        id=location_id,
        book_id=book_id,
        location_type=LocationType.PDF_PAGE.value,
        locator=str(page_number),
        page_number=page_number,
        position_percent=percent,
    )


def epub_location(
    book_id: int,
    href: str,
    index: int,
    total_chapters: int,
    *,
    chapter_title: str | None = None,
    text_offset: int = 0,
    location_id: int | None = None,
) -> LocationDTO:
    # Chapter-based progress; reaching last chapter counts as near end.
    percent = compute_progress_percent(index + 1, total_chapters)
    locator = f"{href}#{text_offset}" if text_offset else href
    return LocationDTO(
        id=location_id,
        book_id=book_id,
        location_type=LocationType.EPUB_POSITION.value,
        locator=locator,
        chapter_title=chapter_title,
        position_percent=percent,
    )


def parse_epub_locator(locator: str) -> tuple[str, int]:
    if "#" in locator:
        href, offset = locator.rsplit("#", 1)
        try:
            return href, int(offset)
        except ValueError:
            return locator, 0
    return locator, 0
