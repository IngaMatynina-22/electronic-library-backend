"""Logging setup for the library backend."""

from __future__ import annotations

import logging
from logging import Logger


def setup_logging(level: int = logging.INFO) -> Logger:
    """Configure root logger once and return the app logger."""
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        root.addHandler(handler)
    root.setLevel(level)
    return logging.getLogger("library")
