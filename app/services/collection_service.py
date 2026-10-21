"""Collection management service."""

from __future__ import annotations

from app.core.database import Database
from app.core.exceptions import ValidationError
from app.models.collection import Collection
from app.repositories.collection_repository import CollectionRepository
from app.schemas.dtos import BookDTO, CollectionDTO
from app.schemas.mappers import to_book_dto, to_collection_dto
from app.services.ownership import require_owned_book, require_owned_collection
from app.utils.dates import ensure_naive_utc


class CollectionService:
    def __init__(self, database: Database, auth=None) -> None:
        self.db = database
        self.auth = auth

    def _uid(self) -> int:
        return self.auth.require_user_id()

    def create(self, name: str, description: str | None = None) -> CollectionDTO:
        uid = self._uid()
        cleaned = (name or "").strip()
        if not cleaned:
            raise ValidationError("Collection name is required")
        with self.db.session_scope() as session:
            repo = CollectionRepository(session)
            if repo.get_by_name(cleaned, user_id=uid):
                raise ValidationError(f"Collection '{cleaned}' already exists")
            collection = Collection(user_id=uid, name=cleaned, description=description)
            repo.add(collection)
            return to_collection_dto(collection, book_count=0)

    def get(self, collection_id: int) -> CollectionDTO:
        uid = self._uid()
        with self.db.session_scope() as session:
            repo = CollectionRepository(session)
            collection = require_owned_collection(session, collection_id, uid)
            return to_collection_dto(collection, book_count=repo.book_count(collection_id))

    def list(self) -> list[CollectionDTO]:
        uid = self._uid()
        with self.db.session_scope() as session:
            repo = CollectionRepository(session)
            return [
                to_collection_dto(c, book_count=len(c.books or []))
                for c in repo.list_all(user_id=uid)
            ]

    def update(
        self,
        collection_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> CollectionDTO:
        uid = self._uid()
        with self.db.session_scope() as session:
            repo = CollectionRepository(session)
            collection = require_owned_collection(session, collection_id, uid)
            if name is not None:
                cleaned = name.strip()
                if not cleaned:
                    raise ValidationError("Collection name is required")
                other = repo.get_by_name(cleaned, user_id=uid)
                if other and other.id != collection_id:
                    raise ValidationError(f"Collection '{cleaned}' already exists")
                collection.name = cleaned
            if description is not None:
                collection.description = description
            collection.updated_at = ensure_naive_utc()
            session.flush()
            return to_collection_dto(collection, book_count=repo.book_count(collection_id))

    def delete(self, collection_id: int) -> None:
        uid = self._uid()
        with self.db.session_scope() as session:
            collection = require_owned_collection(session, collection_id, uid)
            CollectionRepository(session).delete(collection)

    def add_book(self, collection_id: int, book_id: int) -> CollectionDTO:
        uid = self._uid()
        with self.db.session_scope() as session:
            repo = CollectionRepository(session)
            collection = require_owned_collection(session, collection_id, uid)
            book = require_owned_book(session, book_id, uid)
            repo.add_book(collection, book)
            return to_collection_dto(collection, book_count=repo.book_count(collection_id))

    def remove_book(self, collection_id: int, book_id: int) -> CollectionDTO:
        uid = self._uid()
        with self.db.session_scope() as session:
            repo = CollectionRepository(session)
            collection = require_owned_collection(session, collection_id, uid)
            book = require_owned_book(session, book_id, uid)
            repo.remove_book(collection, book)
            return to_collection_dto(collection, book_count=repo.book_count(collection_id))

    def list_books(self, collection_id: int) -> list[BookDTO]:
        uid = self._uid()
        with self.db.session_scope() as session:
            collection = require_owned_collection(session, collection_id, uid)
            return [to_book_dto(b) for b in collection.books]
