"""Reader navigation and progress persistence tests."""

from __future__ import annotations


def test_reader_pdf_progress_persists(container, sample_pdf):
    imported = container.imports.import_file(sample_pdf)
    book_id = imported.book_id

    opened = container.reader.open_book(book_id)
    assert opened["total_units"] == 3

    location = opened["location"]
    next_loc = container.reader.get_next_location(book_id, location)
    assert next_loc is not None
    assert next_loc.page_number == 2

    progress = container.reader.save_position(book_id, next_loc)
    assert progress.current_page == 2
    assert progress.progress_percent > 0

    container.reader.close_book(book_id, next_loc)

    # New reader open should restore last position
    opened2 = container.reader.open_book(book_id)
    restored = opened2["progress"]
    assert restored.current_page == 2
    container.reader.close_book(book_id)


def test_reader_epub_toc_and_content(container, sample_epub):
    imported = container.imports.import_file(sample_epub)
    book_id = imported.book_id
    container.reader.open_book(book_id)
    toc = container.reader.get_toc(book_id)
    assert toc
    page = container.reader.get_content(book_id, toc[0].location)
    assert page.content_type == "html"
    assert "Chapter" in page.content or "Hello" in page.extra.get("plain_text", "")
    container.reader.close_book(book_id)


def test_reading_sessions(container, sample_pdf):
    imported = container.imports.import_file(sample_pdf)
    book_id = imported.book_id
    session = container.reading.start_session(book_id)
    assert session.ended_at is None
    finished = container.reading.finish_session(book_id, session_id=session.id)
    assert finished.ended_at is not None
    assert finished.duration_seconds is not None
    history = container.reading.get_history(book_id)
    assert len(history) >= 1
