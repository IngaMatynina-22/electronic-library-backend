"""Application configuration and data-directory paths."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AppConfig:
    """Central configuration for the local library backend."""

    data_dir: Path
    max_file_size_bytes: int = 500 * 1024 * 1024  # 500 MB
    supported_extensions: tuple[str, ...] = (".pdf", ".epub")

    db_path: Path = field(init=False)
    books_dir: Path = field(init=False)
    covers_dir: Path = field(init=False)
    cache_dir: Path = field(init=False)
    backups_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        self.data_dir = Path(self.data_dir).resolve()
        self.db_path = self.data_dir / "library.db"
        self.books_dir = self.data_dir / "books"
        self.covers_dir = self.data_dir / "covers"
        self.cache_dir = self.data_dir / "cache"
        self.backups_dir = self.data_dir / "backups"

    def ensure_directories(self) -> None:
        """Create data directories if they do not exist."""
        for path in (
            self.data_dir,
            self.books_dir,
            self.covers_dir,
            self.cache_dir,
            self.backups_dir,
            self.cache_dir / "extracted_content",
        ):
            path.mkdir(parents=True, exist_ok=True)

    @classmethod
    def default(cls, project_root: Path | None = None) -> AppConfig:
        """Build config with data/ next to the project root."""
        if project_root is None:
            project_root = Path(__file__).resolve().parents[2]
        return cls(data_dir=project_root / "data")
