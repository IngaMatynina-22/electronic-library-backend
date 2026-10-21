"""Export quotes, notes, and knowledge base to Markdown/JSON."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import Database
from app.models.book import Book
from app.models.note import Note
from app.models.quote import Quote


class ExportService:
    def __init__(self, database: Database, auth=None) -> None:
        self.db = database
        self.auth = auth

    def _uid(self) -> int:
        return self.auth.require_user_id()

    def export_knowledge(
        self,
        destination: str | Path,
        *,
        format: str = "markdown",
        book_id: int | None = None,
        tag: str | None = None,
    ) -> str:
        fmt = format.lower()
        if fmt not in ("markdown", "md", "json"):
            fmt = "markdown"
        data = self._collect(book_id=book_id, tag=tag, user_id=self._uid())
        dest = Path(destination)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if fmt == "json":
            dest.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        else:
            dest.write_text(self._to_markdown(data), encoding="utf-8")
        return str(dest)

    def export_quotes_markdown(self, destination: str | Path, book_id: int | None = None) -> str:
        return self.export_knowledge(destination, format="markdown", book_id=book_id)

    def _collect(self, *, book_id: int | None, tag: str | None, user_id: int) -> dict:
        from app.models.book import Book

        with self.db.session_scope() as session:
            q_stmt = (
                select(Quote)
                .join(Book, Book.id == Quote.book_id)
                .where(Book.user_id == user_id)
                .options(selectinload(Quote.tags), selectinload(Quote.book))
            )
            n_stmt = (
                select(Note)
                .join(Book, Book.id == Note.book_id)
                .where(Book.user_id == user_id)
                .options(
                    selectinload(Note.tags),
                    selectinload(Note.book),
                    selectinload(Note.related_notes),
                )
            )
            if book_id is not None:
                q_stmt = q_stmt.where(Quote.book_id == book_id)
                n_stmt = n_stmt.where(Note.book_id == book_id)
            quotes = list(session.scalars(q_stmt).unique().all())
            notes = list(session.scalars(n_stmt).unique().all())
            if tag:
                tnorm = tag.lower()
                quotes = [q for q in quotes if any(t.name.lower() == tnorm for t in q.tags)]
                notes = [n for n in notes if any(t.name.lower() == tnorm for t in n.tags)]

            return {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "quotes": [
                    {
                        "id": q.id,
                        "book_id": q.book_id,
                        "book_title": q.book.title if q.book else None,
                        "text": q.text,
                        "note": q.note,
                        "highlight_type": getattr(q, "highlight_type", "general"),
                        "color": getattr(q, "color", None),
                        "page_number": q.page_number,
                        "chapter_title": q.chapter_title,
                        "tags": [t.name for t in q.tags],
                    }
                    for q in quotes
                ],
                "notes": [
                    {
                        "id": n.id,
                        "book_id": n.book_id,
                        "book_title": n.book.title if n.book else None,
                        "title": n.title,
                        "content": n.content,
                        "tags": [t.name for t in n.tags],
                        "related_note_ids": [r.id for r in n.related_notes],
                    }
                    for n in notes
                ],
            }

    @staticmethod
    def _to_markdown(data: dict) -> str:
        lines = ["# Knowledge export", "", f"_Exported: {data['exported_at']}_", ""]
        lines.append("## Quotes")
        lines.append("")
        for q in data["quotes"]:
            title = q.get("book_title") or f"Book {q['book_id']}"
            lines.append(f"### {title}")
            lines.append("")
            lines.append(f"> {q['text']}")
            lines.append("")
            meta = []
            if q.get("highlight_type"):
                meta.append(f"type: `{q['highlight_type']}`")
            if q.get("page_number"):
                meta.append(f"page {q['page_number']}")
            if q.get("tags"):
                meta.append("tags: " + ", ".join(f"`{t}`" for t in q["tags"]))
            if meta:
                lines.append("- " + " · ".join(meta))
                lines.append("")
            if q.get("note"):
                lines.append(f"_Note:_ {q['note']}")
                lines.append("")
        lines.append("## Notes")
        lines.append("")
        for n in data["notes"]:
            title = n.get("title") or f"Note {n['id']}"
            book = n.get("book_title") or f"Book {n['book_id']}"
            lines.append(f"### {title} ({book})")
            lines.append("")
            lines.append(n["content"])
            lines.append("")
            if n.get("tags"):
                lines.append("Tags: " + ", ".join(f"`{t}`" for t in n["tags"]))
                lines.append("")
        return "\n".join(lines)
