"""FTS5 content indexing for books, pages, quotes, notes."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import text

from app.core.database import Database
from app.models.book import Book
from app.models.note import Note
from app.models.quote import Quote
from app.readers.content_normalizer import normalize_plain_text
from app.readers.reader_factory import ReaderFactory
from app.storage.path_resolver import PathResolver

logger = logging.getLogger(__name__)


def _fts_query(raw: str) -> str:
    """Build a safe FTS5 MATCH query from user input."""
    tokens = [t for t in raw.replace('"', " ").split() if t]
    if not tokens:
        return '""'
    return " ".join(f'"{t}"' for t in tokens)


class ContentIndexService:
    def __init__(self, database: Database, path_resolver: PathResolver) -> None:
        self.db = database
        self.paths = path_resolver

    def reindex_book(self, book_id: int) -> int:
        """Index book metadata + full content. Returns number of content chunks."""
        with self.db.session_scope() as session:
            book = session.get(Book, book_id)
            if book is None:
                return 0
            authors = ", ".join(a.name for a in (book.authors or []))
            session.execute(text("DELETE FROM books_fts WHERE book_id = :id"), {"id": book_id})
            session.execute(
                text(
                    "INSERT INTO books_fts(book_id, title, description, authors) "
                    "VALUES (:id, :title, :desc, :authors)"
                ),
                {
                    "id": book_id,
                    "title": book.title or "",
                    "desc": book.description or "",
                    "authors": authors,
                },
            )
            file_path = self.paths.resolve(book.file_path)
            fmt = book.format

        chunks = 0
        if file_path and file_path.is_file():
            chunks = self._index_file_content(book_id, file_path, fmt)

        with self.db.session_scope() as session:
            from sqlalchemy import select

            for q in session.scalars(select(Quote).where(Quote.book_id == book_id)).all():
                self._upsert_quote(session, q)
            for n in session.scalars(select(Note).where(Note.book_id == book_id)).all():
                self._upsert_note(session, n)
        return chunks
    def reindex_all(self) -> int:
        with self.db.session_scope() as session:
            ids = [r[0] for r in session.execute(text("SELECT id FROM books")).all()]
        total = 0
        for book_id in ids:
            total += self.reindex_book(book_id)
        return total

    def remove_book(self, book_id: int) -> None:
        with self.db.session_scope() as session:
            for table in ("books_fts", "content_fts", "quotes_fts", "notes_fts"):
                col = "book_id"
                session.execute(text(f"DELETE FROM {table} WHERE {col} = :id"), {"id": book_id})

    def index_quote(self, quote_id: int) -> None:
        with self.db.session_scope() as session:
            q = session.get(Quote, quote_id)
            if q:
                self._upsert_quote(session, q)

    def remove_quote(self, quote_id: int) -> None:
        with self.db.session_scope() as session:
            session.execute(text("DELETE FROM quotes_fts WHERE quote_id = :id"), {"id": quote_id})

    def index_note(self, note_id: int) -> None:
        with self.db.session_scope() as session:
            n = session.get(Note, note_id)
            if n:
                self._upsert_note(session, n)

    def remove_note(self, note_id: int) -> None:
        with self.db.session_scope() as session:
            session.execute(text("DELETE FROM notes_fts WHERE note_id = :id"), {"id": note_id})

    def upsert_content_chunk(
        self,
        book_id: int,
        page_or_chapter: str,
        locator: str,
        body: str,
    ) -> None:
        body = normalize_plain_text(body or "")
        if not body:
            return
        with self.db.session_scope() as session:
            session.execute(
                text(
                    "DELETE FROM content_fts WHERE book_id = :bid AND locator = :loc"
                ),
                {"bid": book_id, "loc": locator},
            )
            session.execute(
                text(
                    "INSERT INTO content_fts(book_id, page_or_chapter, locator, body) "
                    "VALUES (:bid, :poc, :loc, :body)"
                ),
                {"bid": book_id, "poc": page_or_chapter, "loc": locator, "body": body},
            )

    def _index_file_content(self, book_id: int, file_path: Path, fmt: str) -> int:
        with self.db.session_scope() as session:
            session.execute(text("DELETE FROM content_fts WHERE book_id = :id"), {"id": book_id})

        chunks = 0
        try:
            reader = ReaderFactory.create(file_path, fmt)
            reader.open()
            try:
                total = reader.get_total_units()
                loc = reader.make_start_location(book_id)
                for _ in range(total):
                    page = reader.get_content(book_id, loc)
                    body = page.content
                    if page.content_type == "html":
                        body = page.extra.get("plain_text") or body
                    body = normalize_plain_text(body or "")
                    if body:
                        poc = (
                            str(page.page_number)
                            if page.page_number
                            else (page.chapter_title or page.location.locator)
                        )
                        self.upsert_content_chunk(
                            book_id, str(poc), page.location.locator, body
                        )
                        chunks += 1
                    nxt = reader.get_next_location(book_id, loc)
                    if nxt is None:
                        break
                    loc = nxt
            finally:
                reader.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Content index failed for book %s: %s", book_id, exc)
        return chunks

    @staticmethod
    def _upsert_quote(session, quote: Quote) -> None:
        session.execute(text("DELETE FROM quotes_fts WHERE quote_id = :id"), {"id": quote.id})
        body = " ".join(filter(None, [quote.text, quote.note]))
        session.execute(
            text(
                "INSERT INTO quotes_fts(quote_id, book_id, body) VALUES (:qid, :bid, :body)"
            ),
            {"qid": quote.id, "bid": quote.book_id, "body": body},
        )

    @staticmethod
    def _upsert_note(session, note: Note) -> None:
        session.execute(text("DELETE FROM notes_fts WHERE note_id = :id"), {"id": note.id})
        body = " ".join(filter(None, [note.title, note.content]))
        session.execute(
            text(
                "INSERT INTO notes_fts(note_id, book_id, body) VALUES (:nid, :bid, :body)"
            ),
            {"nid": note.id, "bid": note.book_id, "body": body},
        )
