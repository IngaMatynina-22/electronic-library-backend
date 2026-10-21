"""Import job repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.import_job import ImportJob
from app.repositories.base import BaseRepository


class ImportJobRepository(BaseRepository[ImportJob]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, ImportJob)

    def list_recent(self, limit: int = 50) -> list[ImportJob]:
        return list(
            self.session.scalars(
                select(ImportJob).order_by(ImportJob.started_at.desc()).limit(limit)
            ).all()
        )
