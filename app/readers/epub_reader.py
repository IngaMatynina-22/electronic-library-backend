"""EPUB reader adapter using EbookLib."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from bs4 import BeautifulSoup
from ebooklib import ITEM_COVER, ITEM_DOCUMENT, ITEM_IMAGE, epub

from app.core.exceptions import CorruptedFileError, FileAccessError
from app.readers.base_reader import BaseReader, ExtractedMetadata
from app.readers.content_normalizer import normalize_plain_text, strip_scripts_and_normalize_html
from app.readers.location_mapper import epub_location, parse_epub_locator
from app.schemas.dtos import ContentPage, LocationDTO, TocEntry

logger = logging.getLogger(__name__)


class EpubReader(BaseReader):
    def __init__(self, file_path: Path) -> None:
        super().__init__(file_path)
        self._book: epub.EpubBook | None = None
        self._spine: list[tuple[str, str]] = []  # (href, title)

    def open(self) -> None:
        try:
            self._book = epub.read_epub(str(self.file_path), options={"ignore_ncx": True})
        except Exception as exc:  # noqa: BLE001
            raise CorruptedFileError(f"Cannot open EPUB: {exc}") from exc
        self._spine = self._build_spine()
        if not self._spine:
            raise CorruptedFileError("EPUB has no readable chapters")

    def close(self) -> None:
        self._book = None
        self._spine = []

    @property
    def book(self) -> epub.EpubBook:
        if self._book is None:
            raise FileAccessError("EPUB document is not open")
        return self._book

    def _build_spine(self) -> list[tuple[str, str]]:
        items: list[tuple[str, str]] = []
        for item_id, _linear in self.book.spine:
            item = self.book.get_item_with_id(item_id)
            if item is None or item.get_type() != ITEM_DOCUMENT:
                continue
            href = item.get_name()
            title = self._guess_title(item) or href
            items.append((href, title))
        if not items:
            for item in self.book.get_items_of_type(ITEM_DOCUMENT):
                href = item.get_name()
                items.append((href, self._guess_title(item) or href))
        return items

    @staticmethod
    def _guess_title(item: epub.EpubItem) -> str | None:
        try:
            content = item.get_content().decode("utf-8", errors="ignore")
            soup = BeautifulSoup(content, "lxml")
            if soup.title and soup.title.string:
                return soup.title.string.strip()
            heading = soup.find(["h1", "h2", "h3"])
            if heading:
                return heading.get_text(strip=True)
        except Exception:  # noqa: BLE001
            return None
        return None

    def get_total_units(self) -> int:
        return len(self._spine)

    def extract_metadata(self) -> ExtractedMetadata:
        title = self.book.get_metadata("DC", "title")
        title_value = title[0][0] if title else self.file_path.stem
        authors_meta = self.book.get_metadata("DC", "creator")
        authors = [a[0] for a in authors_meta] if authors_meta else []
        language_meta = self.book.get_metadata("DC", "language")
        language = language_meta[0][0] if language_meta else None
        publisher_meta = self.book.get_metadata("DC", "publisher")
        publisher = publisher_meta[0][0] if publisher_meta else None
        description_meta = self.book.get_metadata("DC", "description")
        description = description_meta[0][0] if description_meta else None
        date_meta = self.book.get_metadata("DC", "date")
        year = None
        if date_meta:
            match = re.search(r"(19|20)\d{2}", str(date_meta[0][0]))
            if match:
                year = int(match.group(0))
        isbn = None
        for ident in self.book.get_metadata("DC", "identifier") or []:
            value = str(ident[0])
            if "isbn" in value.lower() or re.search(r"\d{10,13}", value):
                isbn = re.sub(r"[^0-9Xx\-]", "", value) or value
                break

        cover_bytes = self._extract_cover()
        return ExtractedMetadata(
            title=str(title_value).strip() or self.file_path.stem,
            authors=[str(a).strip() for a in authors if str(a).strip()],
            description=description,
            language=language,
            publisher=publisher,
            publication_year=year,
            isbn=isbn,
            cover_bytes=cover_bytes,
            page_count=len(self._spine),
            has_text_layer=True,
        )

    def _extract_cover(self) -> bytes | None:
        try:
            for item in self.book.get_items_of_type(ITEM_COVER):
                return item.get_content()
            # Fallback: look for image named cover
            for item in self.book.get_items_of_type(ITEM_IMAGE):
                name = (item.get_name() or "").lower()
                if "cover" in name:
                    return item.get_content()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to extract EPUB cover: %s", exc)
        return None

    def make_start_location(self, book_id: int) -> LocationDTO:
        href, title = self._spine[0]
        return epub_location(book_id, href, 0, len(self._spine), chapter_title=title)

    def get_toc(self, book_id: int) -> list[TocEntry]:
        entries: list[TocEntry] = []
        for index, (href, title) in enumerate(self._spine):
            entries.append(
                TocEntry(
                    title=title,
                    location=epub_location(
                        book_id, href, index, len(self._spine), chapter_title=title
                    ),
                    level=0,
                )
            )
        return entries

    def _index_from_location(self, location: LocationDTO) -> int:
        href, _ = parse_epub_locator(location.locator)
        for index, (spine_href, _) in enumerate(self._spine):
            if spine_href == href or spine_href.endswith(href) or href.endswith(spine_href):
                return index
        return 0

    def get_content(self, book_id: int, location: LocationDTO) -> ContentPage:
        index = self._index_from_location(location)
        href, title = self._spine[index]
        item = self.book.get_item_with_href(href)
        if item is None:
            # Try matching by basename
            for candidate in self.book.get_items_of_type(ITEM_DOCUMENT):
                if candidate.get_name() == href or candidate.get_name().endswith(href):
                    item = candidate
                    break
        if item is None:
            raise FileAccessError(f"EPUB chapter not found: {href}")
        raw = item.get_content().decode("utf-8", errors="ignore")
        html = strip_scripts_and_normalize_html(raw, base_href=href)
        text = normalize_plain_text(BeautifulSoup(raw, "lxml").get_text("\n"))
        loc = epub_location(
            book_id,
            href,
            index,
            len(self._spine),
            chapter_title=title,
            location_id=location.id,
        )
        return ContentPage(
            location=loc,
            content_type="html",
            content=html,
            chapter_title=title,
            total_units=len(self._spine),
            extra={"plain_text": text},
        )

    def get_next_location(self, book_id: int, location: LocationDTO) -> LocationDTO | None:
        index = self._index_from_location(location)
        if index >= len(self._spine) - 1:
            return None
        href, title = self._spine[index + 1]
        return epub_location(book_id, href, index + 1, len(self._spine), chapter_title=title)

    def get_previous_location(self, book_id: int, location: LocationDTO) -> LocationDTO | None:
        index = self._index_from_location(location)
        if index <= 0:
            return None
        href, title = self._spine[index - 1]
        return epub_location(book_id, href, index - 1, len(self._spine), chapter_title=title)
