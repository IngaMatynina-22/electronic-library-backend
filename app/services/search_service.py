"""Search, filter, sort, and FTS5 full-text search."""

from __future__ import annotations

from sqlalchemy import text

from app.core.database import Database
from app.repositories.book_repository import SORT_FIELDS, BookRepository
from app.repositories.note_repository import NoteRepository
from app.repositories.quote_repository import QuoteRepository
from app.repositories.review_repository import ReviewRepository
from app.schemas.dtos import BookDTO, BookFilter, NoteDTO, QuoteDTO, ReviewDTO, SearchHitDTO
from app.schemas.mappers import to_book_dto, to_note_dto, to_quote_dto, to_review_dto
from app.services.content_index_service import _fts_query


class SearchService:
    def __init__(self, database: Database, auth=None) -> None:
        self.db = database
        self.auth = auth

    def _uid(self) -> int:
        return self.auth.require_user_id()

    def search_books(self, query: str, **kwargs) -> list[BookDTO]:
        filters = BookFilter(query=query, **{k: v for k, v in kwargs.items() if hasattr(BookFilter, k)})
        return self.filter_books(filters)

    def filter_books(self, filters: BookFilter | None = None) -> list[BookDTO]:
        uid = self._uid()
        filters = filters or BookFilter()
        filters.user_id = uid
        with self.db.session_scope() as session:
            books = BookRepository(session).list_filtered(filters)
            return [to_book_dto(b) for b in books]

    def sort_books(self, books: list[BookDTO], sort_by: str = "title", sort_desc: bool = False) -> list[BookDTO]:
        key = sort_by if sort_by in SORT_FIELDS else "title"

        def sort_key(book: BookDTO):
            if key == "progress":
                return book.progress.progress_percent if book.progress else -1
            if key == "author":
                return book.authors[0].name.lower() if book.authors else ""
            value = getattr(book, key, None)
            if isinstance(value, str):
                return value.lower()
            return value is not None, value

        return sorted(books, key=sort_key, reverse=sort_desc)

    def search_quotes(self, query: str) -> list[QuoteDTO]:
        uid = self._uid()
        with self.db.session_scope() as session:
            return [
                to_quote_dto(q)
                for q in QuoteRepository(session).search(query)
                if q.book and q.book.user_id == uid
            ]

    def search_notes(self, query: str) -> list[NoteDTO]:
        uid = self._uid()
        with self.db.session_scope() as session:
            from app.models.book import Book

            return [
                to_note_dto(n)
                for n in NoteRepository(session).search(query)
                if (b := session.get(Book, n.book_id)) and b.user_id == uid
            ]

    def search_reviews(self, query: str) -> list[ReviewDTO]:
        uid = self._uid()
        pattern = query.lower()
        with self.db.session_scope() as session:
            from app.models.book import Book
            from sqlalchemy import select
            from app.models.review import Review

            reviews = session.scalars(
                select(Review).join(Book).where(Book.user_id == uid)
            ).all()
            return [
                to_review_dto(r)
                for r in reviews
                if pattern in (r.content or "").lower()
                or pattern in (r.title or "").lower()
            ]

    def search_fulltext(self, query: str, *, limit: int = 50) -> list[SearchHitDTO]:
        """Search book content, metadata, quotes, and notes via FTS5 with snippets."""
        uid = self._uid()
        q = _fts_query(query)
        if q == '""':
            return []
        hits: list[SearchHitDTO] = []
        with self.db.session_scope() as session:
            titles = {
                r[0]: r[1]
                for r in session.execute(
                    text("SELECT id, title FROM books WHERE user_id = :uid"),
                    {"uid": uid},
                ).all()
            }
            allowed = set(titles.keys())

            rows = session.execute(
                text(
                    "SELECT book_id, page_or_chapter, locator, "
                    "snippet(content_fts, 3, '<mark>', '</mark>', '...', 12) AS snip "
                    "FROM content_fts WHERE content_fts MATCH :q LIMIT :lim"
                ),
                {"q": q, "lim": limit},
            ).all()
            for book_id, poc, locator, snip in rows:
                if book_id not in allowed:
                    continue
                hits.append(
                    SearchHitDTO(
                        source="content",
                        book_id=book_id,
                        book_title=titles.get(book_id),
                        snippet=snip or "",
                        locator=locator,
                        page_or_chapter=str(poc) if poc is not None else None,
                    )
                )

            rows = session.execute(
                text(
                    "SELECT book_id, quote_id, "
                    "snippet(quotes_fts, 2, '<mark>', '</mark>', '...', 12) AS snip "
                    "FROM quotes_fts WHERE quotes_fts MATCH :q LIMIT :lim"
                ),
                {"q": q, "lim": limit},
            ).all()
            for book_id, quote_id, snip in rows:
                if book_id not in allowed:
                    continue
                hits.append(
                    SearchHitDTO(
                        source="quote",
                        book_id=book_id,
                        book_title=titles.get(book_id),
                        snippet=snip or "",
                        entity_id=quote_id,
                    )
                )

            rows = session.execute(
                text(
                    "SELECT book_id, note_id, "
                    "snippet(notes_fts, 2, '<mark>', '</mark>', '...', 12) AS snip "
                    "FROM notes_fts WHERE notes_fts MATCH :q LIMIT :lim"
                ),
                {"q": q, "lim": limit},
            ).all()
            for book_id, note_id, snip in rows:
                if book_id not in allowed:
                    continue
                hits.append(
                    SearchHitDTO(
                        source="note",
                        book_id=book_id,
                        book_title=titles.get(book_id),
                        snippet=snip or "",
                        entity_id=note_id,
                    )
                )

            rows = session.execute(
                text(
                    "SELECT book_id, "
                    "snippet(books_fts, 1, '<mark>', '</mark>', '...', 12) AS snip "
                    "FROM books_fts WHERE books_fts MATCH :q LIMIT :lim"
                ),
                {"q": q, "lim": limit},
            ).all()
            for book_id, snip in rows:
                if book_id not in allowed:
                    continue
                hits.append(
                    SearchHitDTO(
                        source="book",
                        book_id=book_id,
                        book_title=titles.get(book_id),
                        snippet=snip or "",
                    )
                )
        return hits[:limit]
