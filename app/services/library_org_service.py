"""Smart library organization: duplicates, bulk edit, metadata I/O, similar books."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import Database
from app.core.exceptions import NotFoundError, ValidationError
from app.models.associations import book_authors, book_genres
from app.models.author import Author, Genre
from app.models.book import Book
from app.repositories.author_repository import AuthorRepository, GenreRepository
from app.repositories.book_repository import BookRepository
from app.schemas.dtos import BookDTO, BookUpdateDTO, DuplicateGroupDTO
from app.schemas.mappers import to_book_dto
from app.utils.strings import normalize_name
from app.utils.validation import validate_rating, validate_status


class LibraryOrgService:
    def __init__(self, database: Database, auth=None) -> None:
        self.db = database
        self.auth = auth

    def _uid(self) -> int:
        return self.auth.require_user_id()

    def find_duplicates(self) -> list[DuplicateGroupDTO]:
        uid = self._uid()
        groups: list[DuplicateGroupDTO] = []
        with self.db.session_scope() as session:
            books = list(
                session.scalars(
                    select(Book)
                    .where(Book.user_id == uid)
                    .options(selectinload(Book.authors))
                ).all()
            )
            by_isbn: dict[str, list[Book]] = defaultdict(list)
            by_title_author: dict[str, list[Book]] = defaultdict(list)
            for b in books:
                if b.isbn:
                    by_isbn[normalize_name(b.isbn)].append(b)
                authors = "|".join(sorted(normalize_name(a.name) for a in b.authors))
                key = f"{normalize_name(b.title)}::{authors}"
                by_title_author[key].append(b)

            for isbn, items in by_isbn.items():
                if len(items) > 1:
                    groups.append(
                        DuplicateGroupDTO(
                            key=isbn,
                            reason="isbn",
                            book_ids=[b.id for b in items],
                            titles=[b.title for b in items],
                        )
                    )
            for key, items in by_title_author.items():
                if len(items) > 1:
                    # skip if already covered solely by same hash pairs — still report
                    groups.append(
                        DuplicateGroupDTO(
                            key=key,
                            reason="title_author",
                            book_ids=[b.id for b in items],
                            titles=[b.title for b in items],
                        )
                    )
        return groups

    def incomplete_metadata(self) -> list[BookDTO]:
        uid = self._uid()
        with self.db.session_scope() as session:
            books = session.scalars(
                select(Book)
                .where(Book.user_id == uid)
                .options(selectinload(Book.authors), selectinload(Book.genres))
            ).all()
            incomplete = []
            for b in books:
                missing = (
                    not b.description
                    or not b.authors
                    or not b.language
                    or b.publication_year is None
                )
                if missing:
                    incomplete.append(to_book_dto(b))
            return incomplete

    def bulk_update(
        self,
        book_ids: list[int],
        *,
        status: str | None = None,
        author_names: list[str] | None = None,
        genre_names: list[str] | None = None,
        rating: int | None = ...,  # type: ignore[assignment]
        is_favorite: bool | None = None,
        is_archived: bool | None = None,
    ) -> int:
        if not book_ids:
            return 0
        if status is not None:
            validate_status(status)
        if rating is not ...:
            validate_rating(rating)
        uid = self._uid()
        updated = 0
        with self.db.session_scope() as session:
            author_repo = AuthorRepository(session)
            genre_repo = GenreRepository(session)
            for bid in book_ids:
                book = BookRepository(session).get_with_relations(bid)
                if book is None or book.user_id != uid:
                    continue
                if status is not None:
                    book.status = status
                if rating is not ...:
                    book.rating = rating
                if is_favorite is not None:
                    book.is_favorite = is_favorite
                if is_archived is not None:
                    book.is_archived = is_archived
                if author_names is not None:
                    book.authors = [
                        author_repo.get_or_create(n) for n in author_names if n.strip()
                    ]
                if genre_names is not None:
                    book.genres = [
                        genre_repo.get_or_create(n) for n in genre_names if n.strip()
                    ]
                updated += 1
            session.flush()
        return updated

    def similar_books(self, book_id: int, *, limit: int = 10) -> list[BookDTO]:
        uid = self._uid()
        with self.db.session_scope() as session:
            book = BookRepository(session).get_with_relations(book_id)
            if book is None or book.user_id != uid:
                raise NotFoundError(f"Book {book_id} not found")
            author_ids = {a.id for a in book.authors}
            genre_ids = {g.id for g in book.genres}
            candidates = session.scalars(
                select(Book)
                .where(Book.id != book_id, Book.user_id == uid)
                .options(selectinload(Book.authors), selectinload(Book.genres), selectinload(Book.progress))
            ).all()
            scored = []
            for c in candidates:
                score = len(author_ids & {a.id for a in c.authors}) * 3
                score += len(genre_ids & {g.id for g in c.genres})
                if score > 0:
                    scored.append((score, c))
            scored.sort(key=lambda x: -x[0])
            return [to_book_dto(c) for _, c in scored[:limit]]

    def export_metadata(self, destination: str | Path, *, format: str = "json") -> str:
        uid = self._uid()
        dest = Path(destination)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with self.db.session_scope() as session:
            books = session.scalars(
                select(Book)
                .where(Book.user_id == uid)
                .options(selectinload(Book.authors), selectinload(Book.genres))
            ).all()
            rows = [
                {
                    "id": b.id,
                    "title": b.title,
                    "authors": [a.name for a in b.authors],
                    "genres": [g.name for g in b.genres],
                    "status": b.status,
                    "rating": b.rating,
                    "isbn": b.isbn,
                    "language": b.language,
                    "publisher": b.publisher,
                    "publication_year": b.publication_year,
                    "description": b.description,
                    "format": b.format,
                    "is_favorite": b.is_favorite,
                    "is_archived": b.is_archived,
                }
                for b in books
            ]
        if format.lower() == "csv":
            if not rows:
                dest.write_text("", encoding="utf-8")
            else:
                fieldnames = list(rows[0].keys())
                with dest.open("w", encoding="utf-8", newline="") as fh:
                    writer = csv.DictWriter(fh, fieldnames=fieldnames)
                    writer.writeheader()
                    for row in rows:
                        flat = dict(row)
                        flat["authors"] = "; ".join(row["authors"])
                        flat["genres"] = "; ".join(row["genres"])
                        writer.writerow(flat)
        else:
            dest.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(dest)

    def import_metadata(self, source: str | Path) -> int:
        path = Path(source)
        if not path.is_file():
            raise ValidationError(f"Metadata file not found: {path}")
        if path.suffix.lower() == ".csv":
            with path.open(encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
            for row in rows:
                if "authors" in row and isinstance(row["authors"], str):
                    row["authors"] = [a.strip() for a in row["authors"].split(";") if a.strip()]
                if "genres" in row and isinstance(row["genres"], str):
                    row["genres"] = [g.strip() for g in row["genres"].split(";") if g.strip()]
        else:
            rows = json.loads(path.read_text(encoding="utf-8"))
        uid = self._uid()
        count = 0
        with self.db.session_scope() as session:
            author_repo = AuthorRepository(session)
            genre_repo = GenreRepository(session)
            for row in rows:
                bid = row.get("id")
                if bid is None:
                    continue
                book = session.get(Book, int(bid))
                if book is None or book.user_id != uid:
                    continue
                for field in (
                    "title",
                    "description",
                    "isbn",
                    "language",
                    "publisher",
                    "status",
                ):
                    if field in row and row[field] not in (None, ""):
                        setattr(book, field, row[field])
                if "publication_year" in row and row["publication_year"] not in (None, ""):
                    book.publication_year = int(row["publication_year"])
                if "rating" in row and row["rating"] not in (None, ""):
                    book.rating = int(row["rating"]) if row["rating"] is not None else None
                if "authors" in row and isinstance(row["authors"], list):
                    book.authors = [author_repo.get_or_create(n) for n in row["authors"]]
                if "genres" in row and isinstance(row["genres"], list):
                    book.genres = [genre_repo.get_or_create(n) for n in row["genres"]]
                count += 1
            session.flush()
        return count
