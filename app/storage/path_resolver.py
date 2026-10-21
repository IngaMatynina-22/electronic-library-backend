"""Centralized path resolution for library data."""

from __future__ import annotations

from pathlib import Path

from app.core.config import AppConfig


class PathResolver:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def resolve(self, path: str | Path | None) -> Path | None:
        if path is None:
            return None
        p = Path(path)
        if p.is_absolute():
            return p
        return (self.config.data_dir / p).resolve()

    def to_relative(self, path: str | Path) -> str:
        p = Path(path).resolve()
        try:
            return p.relative_to(self.config.data_dir).as_posix()
        except ValueError:
            return p.as_posix()

    def book_dir(self, storage_id: str) -> Path:
        return self.config.books_dir / storage_id

    def cover_path(self, book_id: int, extension: str = ".jpg") -> Path:
        ext = extension if extension.startswith(".") else f".{extension}"
        return self.config.covers_dir / f"{book_id}{ext}"

    def cache_dir_for_book(self, book_id: int) -> Path:
        return self.config.cache_dir / "extracted_content" / str(book_id)
