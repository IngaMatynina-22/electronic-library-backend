"""Library and reading statistics + reading goals."""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.database import Database
from app.core.exceptions import NotFoundError, ValidationError
from app.models.associations import book_authors, book_genres
from app.models.author import Author, Genre
from app.models.book import Book
from app.models.enums import ReadingStatus
from app.models.extensions import ReadingGoal
from app.models.note import Note
from app.models.quote import Quote
from app.models.reading_progress import ReadingProgress
from app.models.reading_session import ReadingSession
from app.schemas.dtos import ReadingGoalDTO, StatisticsDTO
from app.utils.progress import compute_progress_percent


class StatisticsService:
    def __init__(self, database: Database, auth=None) -> None:
        self.db = database
        self.auth = auth

    def _uid(self) -> int:
        return self.auth.require_user_id()

    def get_library_stats(self) -> StatisticsDTO:
        return self.get_reading_stats()

    def get_reading_stats(self) -> StatisticsDTO:
        uid = self._uid()
        with self.db.session_scope() as session:
            status_rows = session.execute(
                select(Book.status, func.count(Book.id))
                .where(Book.user_id == uid)
                .group_by(Book.status)
            ).all()
            by_status = {status: count for status, count in status_rows}

            total_books = sum(by_status.values())
            avg_rating = session.scalar(
                select(func.avg(Book.rating)).where(
                    Book.user_id == uid, Book.rating.is_not(None)
                )
            )
            quotes_count = (
                session.scalar(
                    select(func.count(Quote.id))
                    .join(Book, Book.id == Quote.book_id)
                    .where(Book.user_id == uid)
                )
                or 0
            )
            notes_count = (
                session.scalar(
                    select(func.count(Note.id))
                    .join(Book, Book.id == Note.book_id)
                    .where(Book.user_id == uid)
                )
                or 0
            )

            total_seconds = (
                session.scalar(
                    select(func.coalesce(func.sum(ReadingSession.duration_seconds), 0))
                    .join(Book, Book.id == ReadingSession.book_id)
                    .where(
                        Book.user_id == uid,
                        ReadingSession.ended_at.is_not(None),
                        ReadingSession.duration_seconds.is_not(None),
                    )
                )
                or 0
            )
            session_count = (
                session.scalar(
                    select(func.count(ReadingSession.id))
                    .join(Book, Book.id == ReadingSession.book_id)
                    .where(
                        Book.user_id == uid,
                        ReadingSession.ended_at.is_not(None),
                        ReadingSession.duration_seconds.is_not(None),
                    )
                )
                or 0
            )
            avg_session = (
                round(float(total_seconds) / session_count, 2) if session_count else None
            )

            avg_active = session.scalar(
                select(func.avg(ReadingProgress.progress_percent))
                .join(Book, Book.id == ReadingProgress.book_id)
                .where(
                    Book.user_id == uid,
                    Book.status == ReadingStatus.READING.value,
                )
            )

            pages_read = 0
            for prog in session.scalars(
                select(ReadingProgress)
                .join(Book, Book.id == ReadingProgress.book_id)
                .where(Book.user_id == uid)
            ).all():
                if prog.current_page:
                    pages_read += prog.current_page
                elif prog.total_units and prog.progress_percent:
                    pages_read += int(prog.total_units * prog.progress_percent / 100.0)

            activity_by_day: dict[str, int] = defaultdict(int)
            activity_by_month: dict[str, int] = defaultdict(int)
            activity_by_year: dict[str, int] = defaultdict(int)
            progress_history: list[dict] = []
            sessions = session.scalars(
                select(ReadingSession)
                .join(Book, Book.id == ReadingSession.book_id)
                .where(
                    Book.user_id == uid,
                    ReadingSession.ended_at.is_not(None),
                    ReadingSession.duration_seconds.is_not(None),
                )
            ).all()
            for s in sessions:
                day = s.started_at.strftime("%Y-%m-%d")
                month = s.started_at.strftime("%Y-%m")
                year = s.started_at.strftime("%Y")
                activity_by_day[day] += s.duration_seconds or 0
                activity_by_month[month] += s.duration_seconds or 0
                activity_by_year[year] += s.duration_seconds or 0
                progress_history.append(
                    {
                        "book_id": s.book_id,
                        "started_at": s.started_at,
                        "ended_at": s.ended_at,
                        "start_progress": s.start_progress,
                        "end_progress": s.end_progress,
                        "duration_seconds": s.duration_seconds,
                    }
                )
            progress_history.sort(key=lambda x: x["started_at"], reverse=True)

            completed = session.execute(
                select(Book.id, Book.title, ReadingProgress.completed_at)
                .join(ReadingProgress, ReadingProgress.book_id == Book.id)
                .where(
                    Book.user_id == uid,
                    ReadingProgress.completed_at.is_not(None),
                )
                .order_by(ReadingProgress.completed_at.desc())
            ).all()
            completed_history = [
                {"book_id": row.id, "title": row.title, "completed_at": row.completed_at}
                for row in completed
            ]

            top_authors = [
                {"name": name, "count": count}
                for name, count in session.execute(
                    select(Author.name, func.count(book_authors.c.book_id))
                    .select_from(Author)
                    .join(book_authors, book_authors.c.author_id == Author.id)
                    .join(Book, Book.id == book_authors.c.book_id)
                    .where(Book.user_id == uid)
                    .group_by(Author.name)
                    .order_by(func.count(book_authors.c.book_id).desc())
                    .limit(10)
                ).all()
            ]
            genre_map = self._genre_counts(session, uid)
            top_genres = [{"name": k, "count": v} for k, v in list(genre_map.items())[:10]]

            return StatisticsDTO(
                total_books=total_books,
                completed_books=by_status.get(ReadingStatus.COMPLETED.value, 0),
                reading_books=by_status.get(ReadingStatus.READING.value, 0),
                planned_books=by_status.get(ReadingStatus.PLANNED.value, 0),
                paused_books=by_status.get(ReadingStatus.PAUSED.value, 0),
                abandoned_books=by_status.get(ReadingStatus.ABANDONED.value, 0),
                total_reading_seconds=int(total_seconds),
                average_rating=round(float(avg_rating), 2) if avg_rating is not None else None,
                quotes_count=quotes_count,
                notes_count=notes_count,
                books_by_genre=genre_map,  # already user-scoped
                activity_by_day=dict(sorted(activity_by_day.items())),
                activity_by_month=dict(sorted(activity_by_month.items())),
                activity_by_year=dict(sorted(activity_by_year.items())),
                completed_history=completed_history,
                average_active_progress=(
                    round(float(avg_active), 2) if avg_active is not None else None
                ),
                pages_read_estimate=pages_read,
                books_completed_count=by_status.get(ReadingStatus.COMPLETED.value, 0),
                average_session_seconds=avg_session,
                top_authors=top_authors,
                top_genres=top_genres,
                progress_history=progress_history[:100],
            )

    def get_activity_calendar(self, year: int | None = None) -> dict[str, int]:
        stats = self.get_reading_stats()
        if year is None:
            return stats.activity_by_day
        prefix = str(year)
        return {k: v for k, v in stats.activity_by_day.items() if k.startswith(prefix)}

    def set_goal(self, year: int, target_books: int) -> ReadingGoalDTO:
        uid = self._uid()
        if target_books < 1:
            raise ValidationError("target_books must be >= 1")
        with self.db.session_scope() as session:
            goal = session.scalar(
                select(ReadingGoal).where(
                    ReadingGoal.user_id == uid, ReadingGoal.year == year
                )
            )
            if goal is None:
                goal = ReadingGoal(user_id=uid, year=year, target_books=target_books)
                session.add(goal)
            else:
                goal.target_books = target_books
            session.flush()
            return self._goal_dto(session, goal, uid)

    def get_goal(self, year: int) -> ReadingGoalDTO | None:
        uid = self._uid()
        with self.db.session_scope() as session:
            goal = session.scalar(
                select(ReadingGoal).where(
                    ReadingGoal.user_id == uid, ReadingGoal.year == year
                )
            )
            if goal is None:
                return None
            return self._goal_dto(session, goal, uid)

    def list_goals(self) -> list[ReadingGoalDTO]:
        uid = self._uid()
        with self.db.session_scope() as session:
            goals = session.scalars(
                select(ReadingGoal)
                .where(ReadingGoal.user_id == uid)
                .order_by(ReadingGoal.year.desc())
            ).all()
            return [self._goal_dto(session, g, uid) for g in goals]

    def delete_goal(self, year: int) -> None:
        uid = self._uid()
        with self.db.session_scope() as session:
            goal = session.scalar(
                select(ReadingGoal).where(
                    ReadingGoal.user_id == uid, ReadingGoal.year == year
                )
            )
            if goal is None:
                raise NotFoundError(f"Goal for year {year} not found")
            session.delete(goal)

    def get_genre_stats(self) -> dict[str, int]:
        uid = self._uid()
        with self.db.session_scope() as session:
            return self._genre_counts(session, uid)

    @staticmethod
    def _completed_in_year(session, year: int, user_id: int) -> int:
        return (
            session.scalar(
                select(func.count(ReadingProgress.id))
                .join(Book, Book.id == ReadingProgress.book_id)
                .where(
                    Book.user_id == user_id,
                    ReadingProgress.completed_at.is_not(None),
                    func.strftime("%Y", ReadingProgress.completed_at) == str(year),
                )
            )
            or 0
        )

    def _goal_dto(self, session, goal: ReadingGoal, user_id: int) -> ReadingGoalDTO:
        completed = self._completed_in_year(session, goal.year, user_id)
        return ReadingGoalDTO(
            id=goal.id,
            year=goal.year,
            target_books=goal.target_books,
            completed_books=completed,
            progress_percent=compute_progress_percent(completed, goal.target_books),
            created_at=goal.created_at,
        )

    @staticmethod
    def _genre_counts(session, user_id: int) -> dict[str, int]:
        rows = session.execute(
            select(Genre.name, func.count(book_genres.c.book_id))
            .select_from(Genre)
            .join(book_genres, book_genres.c.genre_id == Genre.id)
            .join(Book, Book.id == book_genres.c.book_id)
            .where(Book.user_id == user_id)
            .group_by(Genre.name)
            .order_by(func.count(book_genres.c.book_id).desc())
        ).all()
        return {name: count for name, count in rows}
