"""Reading location, progress, and session repositories."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.reading_location import ReadingLocation
from app.models.reading_progress import ReadingProgress
from app.models.reading_session import ReadingSession
from app.repositories.base import BaseRepository


class ReadingLocationRepository(BaseRepository[ReadingLocation]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, ReadingLocation)


class ReadingProgressRepository(BaseRepository[ReadingProgress]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, ReadingProgress)

    def get_by_book(self, book_id: int) -> ReadingProgress | None:
        stmt = (
            select(ReadingProgress)
            .where(ReadingProgress.book_id == book_id)
            .options(joinedload(ReadingProgress.current_location))
        )
        return self.session.scalars(stmt).unique().first()


class ReadingSessionRepository(BaseRepository[ReadingSession]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, ReadingSession)

    def get_active(self, book_id: int) -> ReadingSession | None:
        return self.session.scalar(
            select(ReadingSession)
            .where(ReadingSession.book_id == book_id, ReadingSession.ended_at.is_(None))
            .order_by(ReadingSession.started_at.desc())
        )

    def list_by_book(self, book_id: int) -> list[ReadingSession]:
        return list(
            self.session.scalars(
                select(ReadingSession)
                .where(ReadingSession.book_id == book_id)
                .order_by(ReadingSession.started_at.desc())
            ).all()
        )

    def list_all(self) -> list[ReadingSession]:
        return list(
            self.session.scalars(
                select(ReadingSession).order_by(ReadingSession.started_at.desc())
            ).all()
        )
