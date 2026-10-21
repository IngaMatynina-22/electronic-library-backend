"""Create the correct reader for a file path or book format."""

from __future__ import annotations

from pathlib import Path

from app.core.exceptions import UnsupportedFormatError
from app.models.enums import BookFormat
from app.readers.base_reader import BaseReader
from app.readers.epub_reader import EpubReader
from app.readers.pdf_reader import PdfReader


class ReaderFactory:
    @staticmethod
    def detect_format(file_path: Path) -> str:
        """Detect format by content signature, not only by extension."""
        path = Path(file_path)
        try:
            with open(path, "rb") as handle:
                header = handle.read(8)
        except OSError as exc:
            raise UnsupportedFormatError(f"Cannot read file: {path}") from exc

        if header.startswith(b"%PDF"):
            return BookFormat.PDF.value
        # EPUB is a ZIP archive; check ZIP magic then epub-ish extension/path
        if header.startswith(b"PK"):
            suffix = path.suffix.lower()
            if suffix == ".epub" or ReaderFactory._zip_looks_like_epub(path):
                return BookFormat.EPUB.value
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return BookFormat.PDF.value
        if suffix == ".epub":
            return BookFormat.EPUB.value
        raise UnsupportedFormatError(f"Unsupported or unrecognized format: {path.name}")

    @staticmethod
    def _zip_looks_like_epub(path: Path) -> bool:
        try:
            import zipfile

            with zipfile.ZipFile(path, "r") as zf:
                names = set(zf.namelist())
                return "mimetype" in names or any(n.endswith(".opf") for n in names)
        except Exception:  # noqa: BLE001
            return False

    @classmethod
    def create(cls, file_path: Path, format_hint: str | None = None) -> BaseReader:
        fmt = (format_hint or cls.detect_format(file_path)).upper()
        if fmt == BookFormat.PDF.value:
            return PdfReader(file_path)
        if fmt == BookFormat.EPUB.value:
            return EpubReader(file_path)
        raise UnsupportedFormatError(f"No reader for format: {fmt}")
