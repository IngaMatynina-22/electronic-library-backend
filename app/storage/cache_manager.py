"""Content cache under data/cache/extracted_content."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from app.core.config import AppConfig
from app.storage.path_resolver import PathResolver

logger = logging.getLogger(__name__)


class CacheManager:
    def __init__(self, config: AppConfig, path_resolver: PathResolver | None = None) -> None:
        self.config = config
        self.paths = path_resolver or PathResolver(config)

    def get_json(self, book_id: int, key: str) -> Any | None:
        path = self._path(book_id, key)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Cache read failed for book %s/%s: %s", book_id, key, exc)
            return None

    def set_json(self, book_id: int, key: str, value: Any) -> None:
        path = self._path(book_id, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def clear_book(self, book_id: int) -> None:
        directory = self.paths.cache_dir_for_book(book_id)
        if directory.exists():
            shutil.rmtree(directory, ignore_errors=True)

    def clear_all(self) -> None:
        root = self.config.cache_dir / "extracted_content"
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
            root.mkdir(parents=True, exist_ok=True)

    def _path(self, book_id: int, key: str) -> Path:
        safe_key = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)
        return self.paths.cache_dir_for_book(book_id) / f"{safe_key}.json"
