"""SQLAlchemy engine and session factory for SQLite."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import AppConfig
from app.models.base import Base


class Database:
    """Owns the SQLite engine and creates short-lived sessions."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.config.ensure_directories()
        url = f"sqlite:///{config.db_path.as_posix()}"
        self.engine: Engine = create_engine(
            url,
            echo=False,
            connect_args={"check_same_thread": False},
        )
        self._configure_sqlite(self.engine)
        self._session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

    @staticmethod
    def _configure_sqlite(engine: Engine) -> None:
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # noqa: ANN001, ARG001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    def create_tables(self) -> None:
        """Create all ORM tables if they do not exist."""
        # Import models so metadata is populated.
        import app.models  # noqa: F401
        import app.models.extensions  # noqa: F401

        Base.metadata.create_all(self.engine)
        from app.core.schema_extensions import ensure_extensions

        ensure_extensions(self.engine)

    def session(self) -> Session:
        """Create a new session. Do not share across threads."""
        return self._session_factory()

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        """Provide a transactional session scope."""
        session = self.session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()

    @staticmethod
    def from_path(db_path: Path) -> Database:
        """Helper used in tests with a temporary database path."""
        config = AppConfig(data_dir=db_path.parent)
        config.db_path = db_path
        return Database(config)
