"""Abstract book reader interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.schemas.dtos import ContentPage, LocationDTO, TocEntry


@dataclass
class ExtractedMetadata:
    title: Optional[str] = None
    authors: list[str] = field(default_factory=list)
    description: Optional[str] = None
    language: Optional[str] = None
    publisher: Optional[str] = None
    publication_year: Optional[int] = None
    isbn: Optional[str] = None
    cover_bytes: Optional[bytes] = None
    page_count: Optional[int] = None
    has_text_layer: bool = True
    warnings: list[str] = field(default_factory=list)


class BaseReader(ABC):
    def __init__(self, file_path: Path) -> None:
        self.file_path = Path(file_path)

    @abstractmethod
    def open(self) -> None:
        ...

    @abstractmethod
    def close(self) -> None:
        ...

    @abstractmethod
    def extract_metadata(self) -> ExtractedMetadata:
        ...

    @abstractmethod
    def get_toc(self, book_id: int) -> list[TocEntry]:
        ...

    @abstractmethod
    def get_content(self, book_id: int, location: LocationDTO) -> ContentPage:
        ...

    @abstractmethod
    def get_next_location(self, book_id: int, location: LocationDTO) -> LocationDTO | None:
        ...

    @abstractmethod
    def get_previous_location(self, book_id: int, location: LocationDTO) -> LocationDTO | None:
        ...

    @abstractmethod
    def get_total_units(self) -> int:
        ...

    @abstractmethod
    def make_start_location(self, book_id: int) -> LocationDTO:
        ...

    def __enter__(self) -> BaseReader:
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        self.close()
