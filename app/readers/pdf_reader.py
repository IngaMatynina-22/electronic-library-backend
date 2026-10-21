"""PDF reader adapter using PyMuPDF."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pymupdf as fitz

from app.core.exceptions import CorruptedFileError, EncryptedFileError, FileAccessError
from app.readers.base_reader import BaseReader, ExtractedMetadata
from app.readers.content_normalizer import normalize_plain_text
from app.readers.location_mapper import pdf_location
from app.schemas.dtos import ContentPage, LocationDTO, TocEntry

logger = logging.getLogger(__name__)


class PdfReader(BaseReader):
    def __init__(self, file_path: Path) -> None:
        super().__init__(file_path)
        self._doc: fitz.Document | None = None

    def open(self) -> None:
        try:
            self._doc = fitz.open(self.file_path)
        except Exception as exc:  # noqa: BLE001
            raise CorruptedFileError(f"Cannot open PDF: {exc}") from exc
        if self._doc.needs_pass:
            self._doc.close()
            self._doc = None
            raise EncryptedFileError("PDF is password-protected")
        if self._doc.page_count <= 0:
            raise CorruptedFileError("PDF has no pages")

    def close(self) -> None:
        if self._doc is not None:
            self._doc.close()
            self._doc = None

    @property
    def doc(self) -> fitz.Document:
        if self._doc is None:
            raise FileAccessError("PDF document is not open")
        return self._doc

    def get_total_units(self) -> int:
        return self.doc.page_count

    def extract_metadata(self) -> ExtractedMetadata:
        meta = self.doc.metadata or {}
        title = (meta.get("title") or "").strip() or self.file_path.stem
        author_raw = (meta.get("author") or "").strip()
        authors = [a.strip() for a in re.split(r"[,;]", author_raw) if a.strip()] if author_raw else []
        year = None
        date_str = meta.get("creationDate") or meta.get("modDate") or ""
        match = re.search(r"(19|20)\d{2}", date_str)
        if match:
            year = int(match.group(0))

        has_text = False
        sample_pages = min(5, self.doc.page_count)
        for i in range(sample_pages):
            text = self.doc.load_page(i).get_text("text")
            if text and text.strip():
                has_text = True
                break

        cover_bytes = None
        try:
            pix = self.doc.load_page(0).get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            cover_bytes = pix.tobytes("jpeg")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to render PDF cover: %s", exc)

        warnings: list[str] = []
        if not has_text:
            warnings.append("PDF appears to be scanned (no text layer). OCR is not available.")

        return ExtractedMetadata(
            title=title,
            authors=authors,
            description=None,
            language=None,
            publisher=(meta.get("producer") or meta.get("creator") or None),
            publication_year=year,
            isbn=None,
            cover_bytes=cover_bytes,
            page_count=self.doc.page_count,
            has_text_layer=has_text,
            warnings=warnings,
        )

    def make_start_location(self, book_id: int) -> LocationDTO:
        return pdf_location(book_id, 1, self.get_total_units())

    def get_toc(self, book_id: int) -> list[TocEntry]:
        toc = self.doc.get_toc(simple=True) or []
        entries: list[TocEntry] = []
        total = self.get_total_units()
        for level, title, page in toc:
            page_number = max(1, int(page))
            entries.append(
                TocEntry(
                    title=title or f"Page {page_number}",
                    location=pdf_location(book_id, page_number, total),
                    level=max(0, int(level) - 1),
                )
            )
        if not entries:
            for page in range(1, total + 1):
                entries.append(
                    TocEntry(
                        title=f"Page {page}",
                        location=pdf_location(book_id, page, total),
                        level=0,
                    )
                )
        return entries

    def _page_from_location(self, location: LocationDTO) -> int:
        if location.page_number:
            return max(1, min(location.page_number, self.get_total_units()))
        try:
            return max(1, min(int(location.locator), self.get_total_units()))
        except (TypeError, ValueError):
            return 1

    def get_content(self, book_id: int, location: LocationDTO) -> ContentPage:
        page_number = self._page_from_location(location)
        page = self.doc.load_page(page_number - 1)
        text = normalize_plain_text(page.get_text("text") or "")
        loc = pdf_location(book_id, page_number, self.get_total_units(), location_id=location.id)
        return ContentPage(
            location=loc,
            content_type="text",
            content=text,
            page_number=page_number,
            total_units=self.get_total_units(),
        )

    def get_next_location(self, book_id: int, location: LocationDTO) -> LocationDTO | None:
        page = self._page_from_location(location)
        if page >= self.get_total_units():
            return None
        return pdf_location(book_id, page + 1, self.get_total_units())

    def get_previous_location(self, book_id: int, location: LocationDTO) -> LocationDTO | None:
        page = self._page_from_location(location)
        if page <= 1:
            return None
        return pdf_location(book_id, page - 1, self.get_total_units())

    def render_page_image(self, page_number: int, zoom: float = 1.5) -> bytes:
        page = self.doc.load_page(max(0, page_number - 1))
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        return pix.tobytes("png")
