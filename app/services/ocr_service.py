"""Optional OCR for scanned PDF pages via pytesseract."""

from __future__ import annotations

import logging
from io import BytesIO

from sqlalchemy import select

from app.core.database import Database
from app.core.exceptions import LibraryError, NotFoundError, UnsupportedFormatError
from app.models.book import Book
from app.models.enums import BookFormat
from app.models.extensions import OcrPage
from app.schemas.dtos import OcrPageDTO
from app.storage.path_resolver import PathResolver
from app.utils.dates import ensure_naive_utc

logger = logging.getLogger(__name__)


class OcrUnavailableError(LibraryError):
    def __init__(self, message: str = "OCR engine (Tesseract) is not available") -> None:
        super().__init__(message, code="ocr_unavailable")


class OcrService:
    def __init__(
        self,
        database: Database,
        path_resolver: PathResolver,
        content_index=None,
        auth=None,
    ) -> None:
        self.db = database
        self.paths = path_resolver
        self.content_index = content_index
        self.auth = auth

    def is_available(self) -> bool:
        try:
            import pytesseract
            from PIL import Image  # noqa: F401

            pytesseract.get_tesseract_version()
            return True
        except Exception:  # noqa: BLE001
            return False

    def detect_scanned_pages(self, book_id: int) -> list[int]:
        """Return page numbers (1-based) that lack a text layer."""
        path, fmt = self._book_pdf_path(book_id)
        import pymupdf as fitz

        doc = fitz.open(path)
        try:
            empty = []
            for i in range(doc.page_count):
                text = (doc.load_page(i).get_text("text") or "").strip()
                if not text:
                    empty.append(i + 1)
            return empty
        finally:
            doc.close()

    def process_book(
        self,
        book_id: int,
        *,
        pages: list[int] | None = None,
        language: str = "eng",
        progress_callback=None,
    ) -> list[OcrPageDTO]:
        if not self.is_available():
            raise OcrUnavailableError()
        path, _ = self._book_pdf_path(book_id)
        import pymupdf as fitz
        import pytesseract
        from PIL import Image

        targets = pages or self.detect_scanned_pages(book_id)
        results: list[OcrPageDTO] = []
        doc = fitz.open(path)
        try:
            total = max(1, len(targets))
            for idx, page_number in enumerate(targets):
                if progress_callback:
                    progress_callback(f"ocr:{page_number}", (idx + 1) / total)
                self._set_status(book_id, page_number, "processing")
                try:
                    page = doc.load_page(page_number - 1)
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    image = Image.open(BytesIO(pix.tobytes("png")))
                    text = pytesseract.image_to_string(image, lang=language) or ""
                    if self.content_index and text.strip():
                        self.content_index.upsert_content_chunk(
                            book_id,
                            str(page_number),
                            str(page_number),
                            text,
                        )
                    status = "completed" if text.strip() else "skipped"
                    self._set_status(book_id, page_number, status)
                    results.append(OcrPageDTO(book_id=book_id, page_number=page_number, status=status))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("OCR failed book=%s page=%s: %s", book_id, page_number, exc)
                    self._set_status(book_id, page_number, "failed", str(exc))
                    results.append(
                        OcrPageDTO(
                            book_id=book_id,
                            page_number=page_number,
                            status="failed",
                            error_message=str(exc),
                        )
                    )
        finally:
            doc.close()
        return results

    def retry_failed(self, book_id: int, **kwargs) -> list[OcrPageDTO]:
        with self.db.session_scope() as session:
            failed = session.scalars(
                select(OcrPage).where(
                    OcrPage.book_id == book_id, OcrPage.status == "failed"
                )
            ).all()
            pages = [p.page_number for p in failed]
        if not pages:
            return []
        return self.process_book(book_id, pages=pages, **kwargs)

    def list_pages(self, book_id: int) -> list[OcrPageDTO]:
        with self.db.session_scope() as session:
            rows = session.scalars(
                select(OcrPage)
                .where(OcrPage.book_id == book_id)
                .order_by(OcrPage.page_number)
            ).all()
            return [
                OcrPageDTO(
                    book_id=r.book_id,
                    page_number=r.page_number,
                    status=r.status,
                    error_message=r.error_message,
                )
                for r in rows
            ]

    def _set_status(
        self, book_id: int, page_number: int, status: str, error: str | None = None
    ) -> None:
        with self.db.session_scope() as session:
            row = session.scalar(
                select(OcrPage).where(
                    OcrPage.book_id == book_id, OcrPage.page_number == page_number
                )
            )
            if row is None:
                row = OcrPage(book_id=book_id, page_number=page_number, status=status)
                session.add(row)
            row.status = status
            row.error_message = error
            row.updated_at = ensure_naive_utc()

    def _book_pdf_path(self, book_id: int):
        uid = self.auth.require_user_id() if self.auth else None
        with self.db.session_scope() as session:
            book = session.get(Book, book_id)
            if book is None or (uid is not None and book.user_id != uid):
                raise NotFoundError(f"Book {book_id} not found")
            if book.format != BookFormat.PDF.value:
                raise UnsupportedFormatError("OCR is only supported for PDF books")
            path = self.paths.resolve(book.file_path)
            fmt = book.format
        if path is None or not path.is_file():
            raise NotFoundError(f"Book file missing for {book_id}")
        return path, fmt
