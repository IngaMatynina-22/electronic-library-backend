"""Backend entry point for PySide6 GUI integration."""

from __future__ import annotations

from pathlib import Path

from app.container import AppContainer, build_container
from app.core.config import AppConfig
from app.core.logging_config import setup_logging


def init_backend(data_dir: str | Path | None = None) -> AppContainer:
    """
    Initialize the local library backend.

    Args:
        data_dir: Optional path to the data directory. Defaults to ./data next to the project.

    Returns:
        AppContainer with all services ready for GUI use.
    """
    setup_logging()
    if data_dir is None:
        config = AppConfig.default()
    else:
        config = AppConfig(data_dir=Path(data_dir))
    return build_container(config)


def main() -> None:
    """Simple smoke check when run as a module."""
    container = init_backend()
    stats = container.statistics.get_library_stats()
    print(f"Library ready. Books: {stats.total_books}")
    print(f"Database: {container.config.db_path}")
    container.shutdown()


if __name__ == "__main__":
    main()
