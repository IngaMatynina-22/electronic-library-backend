"""Cover image extraction and storage."""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

from PIL import Image

from app.core.config import AppConfig
from app.storage.path_resolver import PathResolver

logger = logging.getLogger(__name__)


class CoverManager:
    def __init__(self, config: AppConfig, path_resolver: PathResolver | None = None) -> None:
        self.config = config
        self.paths = path_resolver or PathResolver(config)

    def save_cover_bytes(self, book_id: int, data: bytes, preferred_ext: str = ".jpg") -> str | None:
        if not data:
            return None
        try:
            image = Image.open(BytesIO(data))
            image = image.convert("RGB")
            # Reasonable thumbnail size for library cards
            image.thumbnail((600, 900))
            dest = self.paths.cover_path(book_id, ".jpg")
            dest.parent.mkdir(parents=True, exist_ok=True)
            image.save(dest, format="JPEG", quality=85)
            return self.paths.to_relative(dest)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to save cover for book %s: %s", book_id, exc)
            return None

    def save_cover_file(self, book_id: int, source: Path) -> str | None:
        try:
            return self.save_cover_bytes(book_id, source.read_bytes())
        except OSError as exc:
            logger.warning("Cannot read cover source %s: %s", source, exc)
            return None

    def delete_unused(self, used_relative_paths: set[str]) -> int:
        removed = 0
        for path in self.config.covers_dir.glob("*"):
            if not path.is_file():
                continue
            rel = self.paths.to_relative(path)
            if rel not in used_relative_paths:
                try:
                    path.unlink()
                    removed += 1
                except OSError:
                    pass
        return removed
