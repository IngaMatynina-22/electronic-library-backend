"""Shared repository helpers."""

from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy.orm import Session

from app.models.base import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    def __init__(self, session: Session, model: type[T]) -> None:
        self.session = session
        self.model = model

    def get(self, entity_id: int) -> T | None:
        return self.session.get(self.model, entity_id)

    def add(self, entity: T) -> T:
        self.session.add(entity)
        self.session.flush()
        return entity

    def delete(self, entity: T) -> None:
        self.session.delete(entity)
        self.session.flush()
