"""Helpers for per-user ownership checks."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.book import Book
from app.models.collection import Collection
from app.repositories.book_repository import BookRepository


def require_owned_book(session: Session, book_id: int, user_id: int) -> Book:
    book = BookRepository(session).get_owned(book_id, user_id)
    if book is None:
        raise NotFoundError(f"Book {book_id} not found")
    return book


def require_owned_book_relations(session: Session, book_id: int, user_id: int) -> Book:
    book = BookRepository(session).get_with_relations(book_id)
    if book is None or book.user_id != user_id:
        raise NotFoundError(f"Book {book_id} not found")
    return book


def require_owned_collection(session: Session, collection_id: int, user_id: int) -> Collection:
    collection = session.get(Collection, collection_id)
    if collection is None or collection.user_id != user_id:
        raise NotFoundError(f"Collection {collection_id} not found")
    return collection
