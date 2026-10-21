"""Import, duplicate detection, and book CRUD tests."""

from __future__ import annotations

from app.core.exceptions import NotFoundError, ValidationError
from app.models.enums import ImportStatus
from app.schemas.dtos import BookUpdateDTO


def test_import_pdf(container, sample_pdf):
    result = container.imports.import_file(sample_pdf)
    assert result.success
    assert result.book is not None
    assert result.book.format == "PDF"
    assert result.book.title == "Sample PDF"
    assert any(a.name == "Test Author" for a in result.book.authors)


def test_import_epub(container, sample_epub):
    result = container.imports.import_file(sample_epub)
    assert result.success
    assert result.book.format == "EPUB"
    assert result.book.title == "Sample EPUB"


def test_duplicate_import(container, sample_pdf):
    first = container.imports.import_file(sample_pdf)
    second = container.imports.import_file(sample_pdf)
    assert first.success
    assert not second.success
    assert second.is_duplicate
    assert second.status == ImportStatus.DUPLICATE.value
    assert second.book_id == first.book_id


def test_book_update_and_rating(container, sample_pdf):
    result = container.imports.import_file(sample_pdf)
    book_id = result.book_id
    updated = container.books.update(
        book_id,
        BookUpdateDTO(
            title="Updated Title",
            status="reading",
            author_names=["A", "B"],
            genre_names=["Fiction"],
        ),
    )
    assert updated.title == "Updated Title"
    assert updated.status == "reading"
    assert len(updated.authors) == 2
    assert updated.genres[0].name == "Fiction"

    rated = container.books.set_rating(book_id, 5)
    assert rated.rating == 5

    try:
        container.books.set_rating(book_id, 9)
        assert False, "expected ValidationError"
    except ValidationError:
        pass


def test_delete_cascades_user_data(container, sample_pdf):
    result = container.imports.import_file(sample_pdf)
    book_id = result.book_id
    container.quotes.create(book_id, "A quote")
    container.notes.create(book_id, "A note")
    container.reviews.create(book_id, "Great book", rating=4)

    container.books.delete(book_id)
    try:
        container.books.get(book_id)
        assert False, "expected NotFoundError"
    except NotFoundError:
        pass
    assert container.quotes.list() == []
