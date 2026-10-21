"""Apply ALTER TABLE + FTS5 + user_id backfill after create_all."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

FTS_STATEMENTS = [
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS books_fts USING fts5(
        book_id UNINDEXED, title, description, authors
    )
    """,
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS content_fts USING fts5(
        book_id UNINDEXED, page_or_chapter UNINDEXED, locator UNINDEXED, body
    )
    """,
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS quotes_fts USING fts5(
        quote_id UNINDEXED, book_id UNINDEXED, body
    )
    """,
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
        note_id UNINDEXED, book_id UNINDEXED, body
    )
    """,
]

ALTERS = [
    ("quotes", "highlight_type", "ALTER TABLE quotes ADD COLUMN highlight_type VARCHAR(32) DEFAULT 'general'"),
    ("quotes", "color", "ALTER TABLE quotes ADD COLUMN color VARCHAR(16)"),
    ("books", "user_id", "ALTER TABLE books ADD COLUMN user_id INTEGER"),
    ("collections", "user_id", "ALTER TABLE collections ADD COLUMN user_id INTEGER"),
    ("tags", "user_id", "ALTER TABLE tags ADD COLUMN user_id INTEGER"),
    ("reading_goals", "user_id", "ALTER TABLE reading_goals ADD COLUMN user_id INTEGER"),
    ("reader_preferences", "user_id", "ALTER TABLE reader_preferences ADD COLUMN user_id INTEGER"),
    ("import_jobs", "user_id", "ALTER TABLE import_jobs ADD COLUMN user_id INTEGER"),
]

USER_INDEXES = [
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_book_user_hash ON books(user_id, file_hash)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_collection_user_name ON collections(user_id, name)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_tag_user_normalized ON tags(user_id, normalized_name)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_reading_goal_user_year ON reading_goals(user_id, year)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_reader_pref_user_book ON reader_preferences(user_id, book_id)",
]


def _column_exists(conn, table: str, column: str) -> bool:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return any(r[1] == column for r in rows)


def _table_exists(conn, table: str) -> bool:
    row = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
        {"n": table},
    ).fetchone()
    return row is not None


def _ensure_demo_user(conn) -> int | None:
    """Create demo user for backfill if needed. Returns user id."""
    if not _table_exists(conn, "users"):
        return None
    row = conn.execute(
        text("SELECT id FROM users WHERE normalized_username = 'demo' LIMIT 1")
    ).fetchone()
    if row:
        return int(row[0])
    # Placeholder hash; AuthService will recreate properly on fresh DBs via seed.
    # Use a fixed bcrypt hash for "demo1234" if bcrypt available, else opaque marker.
    try:
        import bcrypt

        pwd = bcrypt.hashpw(b"demo1234", bcrypt.gensalt()).decode("ascii")
    except Exception:  # noqa: BLE001
        pwd = "!"
    conn.execute(
        text(
            "INSERT INTO users (username, normalized_username, password_hash, display_name, created_at) "
            "VALUES ('demo', 'demo', :pwd, 'Demo User', CURRENT_TIMESTAMP)"
        ),
        {"pwd": pwd},
    )
    row = conn.execute(
        text("SELECT id FROM users WHERE normalized_username = 'demo' LIMIT 1")
    ).fetchone()
    return int(row[0]) if row else None


def ensure_extensions(engine: Engine) -> None:
    with engine.begin() as conn:
        for table, column, stmt in ALTERS:
            if _table_exists(conn, table) and not _column_exists(conn, table, column):
                conn.execute(text(stmt))
        for stmt in FTS_STATEMENTS:
            conn.execute(text(stmt))

        demo_id = _ensure_demo_user(conn)
        if demo_id is not None:
            for table in (
                "books",
                "collections",
                "tags",
                "reading_goals",
                "reader_preferences",
                "import_jobs",
            ):
                if _table_exists(conn, table) and _column_exists(conn, table, "user_id"):
                    conn.execute(
                        text(f"UPDATE {table} SET user_id = :uid WHERE user_id IS NULL"),
                        {"uid": demo_id},
                    )

        for stmt in USER_INDEXES:
            try:
                conn.execute(text(stmt))
            except Exception:  # noqa: BLE001
                # Old unique indexes on single columns may conflict until DB recreate
                pass
