"""Quotes, bookmarks, notes, reviews, collections, search."""

from __future__ import annotations

from app.schemas.dtos import BookFilter, LocationDTO


def test_quotes_bookmarks_notes_reviews(container, sample_pdf):
    imported = container.imports.import_file(sample_pdf)
    book_id = imported.book_id
    location = LocationDTO(
        id=None,
        book_id=book_id,
        location_type="pdf_page",
        locator="1",
        page_number=1,
        position_percent=33.33,
    )

    quote = container.quotes.create(book_id, "Memorable line", location=location, note="nice")
    assert quote.text == "Memorable line"
    assert quote.note == "nice"

    bookmark = container.bookmarks.create(book_id, location, title="Start")
    assert bookmark.title == "Start"
    resolved = container.bookmarks.resolve_location(bookmark.id)
    assert resolved is not None
    assert resolved.page_number == 1

    note = container.notes.create(book_id, "General thoughts", title="Thoughts")
    assert note.content == "General thoughts"

    review = container.reviews.create(book_id, "Loved it", title="Review", rating=5)
    assert review.rating == 5

    found = container.quotes.search("Memorable")
    assert len(found) == 1


def test_collections_and_search(container, sample_pdf, sample_epub):
    pdf = container.imports.import_file(sample_pdf)
    epub_result = container.imports.import_file(sample_epub)
    collection = container.collections.create("Favorites", "My list")
    container.collections.add_book(collection.id, pdf.book_id)
    container.collections.add_book(collection.id, epub_result.book_id)

    books = container.collections.list_books(collection.id)
    assert len(books) == 2

    filtered = container.search.filter_books(
        BookFilter(format="PDF", sort_by="title")
    )
    assert len(filtered) == 1
    assert filtered[0].format == "PDF"

    by_query = container.search.search_books("Sample")
    assert len(by_query) >= 2
