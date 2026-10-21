"""Statistics and backup/restore tests."""

from __future__ import annotations

from pathlib import Path


def test_statistics(container, sample_pdf):
    imported = container.imports.import_file(sample_pdf)
    book_id = imported.book_id
    container.books.set_rating(book_id, 4)
    container.quotes.create(book_id, "Quote")
    container.notes.create(book_id, "Note")
    session = container.reading.start_session(book_id)
    container.reading.finish_session(book_id, session_id=session.id)

    stats = container.statistics.get_library_stats()
    assert stats.total_books == 1
    assert stats.quotes_count == 1
    assert stats.notes_count == 1
    assert stats.average_rating == 4.0


def test_backup_and_restore(container, sample_pdf, tmp_path: Path):
    imported = container.imports.import_file(sample_pdf)
    book_id = imported.book_id
    container.quotes.create(book_id, "Keep me")

    backup_path = tmp_path / "backup.zip"
    result = container.backup.create_backup(include_files=True, destination=backup_path)
    assert result.success
    assert backup_path.exists()

    info = container.backup.validate_backup(backup_path)
    assert info["valid"]

    # Delete book then restore
    container.books.delete(book_id)
    assert container.books.list() == []

    restored = container.backup.restore_backup(backup_path, create_safety_backup=False)
    assert restored.success
    books = container.books.list()
    assert len(books) == 1
    assert container.quotes.get_by_book(books[0].id)
