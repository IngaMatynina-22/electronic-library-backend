"""Author and genre repositories."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.author import Author, Genre
from app.repositories.base import BaseRepository
from app.utils.strings import normalize_name


class AuthorRepository(BaseRepository[Author]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Author)

    def get_by_normalized_name(self, name: str) -> Author | None:
        normalized = normalize_name(name)
        return self.session.scalar(
            select(Author).where(Author.normalized_name == normalized)
        )

    def get_or_create(self, name: str) -> Author:
        existing = self.get_by_normalized_name(name)
        if existing:
            return existing
        author = Author(name=name.strip(), normalized_name=normalize_name(name))
        return self.add(author)

    def list_all(self) -> list[Author]:
        return list(self.session.scalars(select(Author).order_by(Author.name)).all())


class GenreRepository(BaseRepository[Genre]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Genre)

    def get_by_normalized_name(self, name: str) -> Genre | None:
        normalized = normalize_name(name)
        return self.session.scalar(
            select(Genre).where(Genre.normalized_name == normalized)
        )

    def get_or_create(self, name: str) -> Genre:
        existing = self.get_by_normalized_name(name)
        if existing:
            return existing
        genre = Genre(name=name.strip(), normalized_name=normalize_name(name))
        return self.add(genre)

    def list_all(self) -> list[Genre]:
        return list(self.session.scalars(select(Genre).order_by(Genre.name)).all())
