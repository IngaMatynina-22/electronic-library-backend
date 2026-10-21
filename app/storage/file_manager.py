"""File copy, hash, and availability helpers."""

from __future__ import annotations

import hashlib
import logging
import shutil
import uuid
from pathlib import Path

from app.core.config import AppConfig
from app.core.exceptions import DiskSpaceError, FileAccessError, UnsupportedFormatError
from app.storage.path_resolver import PathResolver

logger = logging.getLogger(__name__)


class FileManager:
    def __init__(self, config: AppConfig, path_resolver: PathResolver | None = None) -> None:
        self.config = config
        self.paths = path_resolver or PathResolver(config)

    def compute_hash(self, file_path: Path, chunk_size: int = 1024 * 1024) -> str:
        digest = hashlib.sha256()
        try:
            with open(file_path, "rb") as handle:
                while True:
                    chunk = handle.read(chunk_size)
                    if not chunk:
                        break
                    digest.update(chunk)
        except OSError as exc:
            raise FileAccessError(f"Cannot read file for hashing: {file_path}") from exc
        return digest.hexdigest()

    def validate_source(self, source_path: Path) -> Path:
        path = Path(source_path)
        if not path.exists():
            raise FileAccessError(f"File not found: {path}")
        if not path.is_file():
            raise FileAccessError(f"Path is not a file: {path}")
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise FileAccessError(f"Cannot access file: {path}") from exc
        if size <= 0:
            raise FileAccessError(f"File is empty: {path}")
        if size > self.config.max_file_size_bytes:
            raise FileAccessError(
                f"File exceeds maximum size of {self.config.max_file_size_bytes} bytes"
            )
        suffix = path.suffix.lower()
        if suffix not in self.config.supported_extensions:
            raise UnsupportedFormatError(f"Unsupported extension: {suffix}")
        return path.resolve()

    def copy_to_library(self, source_path: Path, format_ext: str) -> tuple[str, Path]:
        """Copy source into data/books/<uuid>/original.<ext>. Returns (storage_id, dest)."""
        source = self.validate_source(source_path)
        storage_id = uuid.uuid4().hex
        dest_dir = self.paths.book_dir(storage_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        ext = format_ext.lower().lstrip(".")
        dest = dest_dir / f"original.{ext}"
        try:
            shutil.copy2(source, dest)
        except OSError as exc:
            shutil.rmtree(dest_dir, ignore_errors=True)
            if getattr(exc, "errno", None) == 28:
                raise DiskSpaceError("Not enough disk space to copy book file") from exc
            raise FileAccessError(f"Failed to copy file into library: {exc}") from exc
        if not dest.exists() or dest.stat().st_size != source.stat().st_size:
            shutil.rmtree(dest_dir, ignore_errors=True)
            raise FileAccessError("File copy verification failed")
        return storage_id, dest

    def is_available(self, file_path: str | Path) -> bool:
        path = self.paths.resolve(file_path)
        if path is None:
            return False
        return path.is_file()

    def delete_book_files(self, file_path: str | Path | None, cover_path: str | Path | None = None) -> None:
        """Delete internal library copy and cover. Never touches external originals."""
        if file_path:
            path = self.paths.resolve(file_path)
            if path and path.exists():
                parent = path.parent
                try:
                    path.unlink(missing_ok=True)
                    if parent.is_dir() and parent.parent == self.config.books_dir:
                        shutil.rmtree(parent, ignore_errors=True)
                except OSError as exc:
                    logger.warning("Failed to delete book file %s: %s", path, exc)
        if cover_path:
            cpath = self.paths.resolve(cover_path)
            if cpath and cpath.exists():
                try:
                    cpath.unlink(missing_ok=True)
                except OSError as exc:
                    logger.warning("Failed to delete cover %s: %s", cpath, exc)
