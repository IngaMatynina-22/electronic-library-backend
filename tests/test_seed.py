"""Tests for the localized demo library corpus."""

from __future__ import annotations

import pymupdf as fitz
from ebooklib import ITEM_DOCUMENT, epub

from app.seed import generate_seed_sources


def test_seed_sources_are_complete_ukrainian_books(tmp_path):
    files = generate_seed_sources(tmp_path)

    assert len(files) == 6

    with fitz.open(files["dune_pdf"]) as pdf:
        assert pdf.page_count == 5
        assert pdf.metadata["title"] == "Місто над туманом"
        pdf_text = "\n".join(page.get_text() for page in pdf).replace("\xa0", " ")
        assert "Розділ 5" in pdf_text

    book = epub.read_epub(str(files["solaris_epub"]))
    chapters = [
        item.get_content().decode("utf-8")
        for item in book.get_items_of_type(ITEM_DOCUMENT)
        if item.get_name().startswith("chap")
    ]
    assert len(chapters) == 3
    assert "Голос у мушлі" in "".join(chapters)
    assert "Світло" in chapters[-1]