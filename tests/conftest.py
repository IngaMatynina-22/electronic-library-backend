"""Pytest fixtures for the library backend."""

from __future__ import annotations

from pathlib import Path

import pymupdf as fitz
import pytest
from ebooklib import epub

from app.container import AppContainer, build_container
from app.core.config import AppConfig


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    return tmp_path / "data"


@pytest.fixture
def container(data_dir: Path) -> AppContainer:
    config = AppConfig(data_dir=data_dir)
    c = build_container(config)
    c.auth.register("testuser", "testpass123", display_name="Test User")
    return c


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "sample.pdf"
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i + 1} of the sample book.")
    doc.set_metadata({"title": "Sample PDF", "author": "Test Author"})
    doc.save(path)
    doc.close()
    return path


@pytest.fixture
def sample_epub(tmp_path: Path) -> Path:
    path = tmp_path / "sample.epub"
    book = epub.EpubBook()
    book.set_identifier("id-sample-epub")
    book.set_title("Sample EPUB")
    book.set_language("en")
    book.add_author("EPUB Author")

    chapter = epub.EpubHtml(title="Chapter 1", file_name="chap1.xhtml", lang="en")
    chapter.content = (
        "<html><head><title>Chapter 1</title></head>"
        "<body><h1>Chapter 1</h1><p>Hello from EPUB.</p></body></html>"
    )
    book.add_item(chapter)
    book.toc = (epub.Link("chap1.xhtml", "Chapter 1", "chap1"),)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", chapter]
    epub.write_epub(str(path), book)
    return path
