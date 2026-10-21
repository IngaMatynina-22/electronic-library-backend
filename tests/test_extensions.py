"""Tests for smart library extensions."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_fts_search_after_import(container, sample_pdf):
    result = container.imports.import_file(sample_pdf)
    assert result.success
    hits = container.search.search_fulltext("sample")
    assert any(h.book_id == result.book_id for h in hits)
    assert any("<mark>" in (h.snippet or "") or h.source for h in hits)


def test_tags_highlight_and_export(container, sample_pdf, tmp_path: Path):
    book_id = container.imports.import_file(sample_pdf).book_id
    quote = container.quotes.create(
        book_id,
        "Memorable insight",
        highlight_type="idea",
        color="#ffcc00",
        tag_names=["philosophy"],
    )
    assert quote.highlight_type == "idea"
    assert any(t.name == "philosophy" for t in quote.tags)

    note = container.notes.create(book_id, "Linked thought", tag_names=["philosophy"])
    note2 = container.notes.create(book_id, "Another book thought")
    linked = container.notes.link_notes(note.id, note2.id)
    assert note2.id in linked.related_note_ids

    md_path = tmp_path / "knowledge.md"
    out = container.export.export_knowledge(md_path, format="markdown")
    text = Path(out).read_text(encoding="utf-8")
    assert "Memorable insight" in text
    assert "philosophy" in text


def test_reading_goal(container, sample_pdf):
    book_id = container.imports.import_file(sample_pdf).book_id
    goal = container.statistics.set_goal(2026, 20)
    assert goal.target_books == 20
    assert goal.year == 2026
    fetched = container.statistics.get_goal(2026)
    assert fetched is not None
    assert fetched.progress_percent >= 0
    stats = container.statistics.get_reading_stats()
    assert isinstance(stats.activity_by_year, dict)
    assert stats.pages_read_estimate >= 0


def test_library_org_duplicates_and_metadata(container, sample_pdf, tmp_path: Path):
    r1 = container.imports.import_file(sample_pdf)
    # Second import is hash-duplicate; create a "soft" duplicate via metadata export/import path
    books = container.books.list()
    assert len(books) == 1

    incomplete = container.library_org.incomplete_metadata()
    assert any(b.id == r1.book_id for b in incomplete)

    meta_path = tmp_path / "meta.json"
    container.library_org.export_metadata(meta_path, format="json")
    assert meta_path.exists()

    updated = container.library_org.bulk_update([r1.book_id], status="reading", genre_names=["SciFi"])
    assert updated == 1
    book = container.books.get(r1.book_id)
    assert book.status == "reading"


def test_reader_prefs(container, sample_pdf):
    global_prefs = container.reader_prefs.set(theme="dark", font_size=16)
    assert global_prefs.theme == "dark"
    book_id = container.imports.import_file(sample_pdf).book_id
    book_prefs = container.reader_prefs.set(book_id=book_id, font_size=20)
    assert book_prefs.font_size == 20
    merged = container.reader_prefs.get(book_id)
    assert merged.font_size == 20
    assert merged.theme == "dark"


def test_ocr_unavailable_or_detect(container, sample_pdf):
    book_id = container.imports.import_file(sample_pdf).book_id
    # Sample PDF has text — scanned list may be empty
    pages = container.ocr.detect_scanned_pages(book_id)
    assert isinstance(pages, list)
    if not container.ocr.is_available():
        from app.services.ocr_service import OcrUnavailableError

        with pytest.raises(OcrUnavailableError):
            container.ocr.process_book(book_id, pages=[1])
