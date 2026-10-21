"""Maximal demo seed for the personal library database.

Usage:
    python -m app.seed
    python -m app.seed --force
    python -m app.seed --data-dir PATH --force
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pymupdf as fitz
from ebooklib import epub

from app.container import AppContainer, build_container
from app.core.config import AppConfig
from app.core.logging_config import setup_logging
from app.models.enums import ImportStatus, LocationType
from app.models.extensions import OcrPage
from app.models.import_job import ImportJob
from app.models.base import utcnow
from app.schemas.dtos import BookUpdateDTO, LocationDTO
from app.utils.dates import ensure_naive_utc


def _make_pdf(
    path: Path,
    *,
    title: str,
    author: str,
    pages: list[str],
    publisher: str | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        # Multi-line text
        y = 72
        for line in text.split("\n"):
            page.insert_text((72, y), line[:110])
            y += 16
    meta = {"title": title, "author": author}
    if publisher:
        meta["producer"] = publisher
    doc.set_metadata(meta)
    doc.save(path)
    doc.close()
    return path


def _make_epub(
    path: Path,
    *,
    title: str,
    author: str,
    chapters: list[tuple[str, str]],
    language: str = "en",
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    book = epub.EpubBook()
    book.set_identifier(f"seed-{path.stem}")
    book.set_title(title)
    book.set_language(language)
    book.add_author(author)

    items = []
    toc = []
    for i, (ch_title, body) in enumerate(chapters, start=1):
        fname = f"chap{i}.xhtml"
        chapter = epub.EpubHtml(title=ch_title, file_name=fname, lang=language)
        chapter.content = (
            f"<html><head><title>{ch_title}</title></head>"
            f"<body><h1>{ch_title}</h1><p>{body}</p></body></html>"
        )
        book.add_item(chapter)
        items.append(chapter)
        toc.append(epub.Link(fname, ch_title, f"chap{i}"))

    book.toc = tuple(toc)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", *items]
    epub.write_epub(str(path), book)
    return path


def _pdf_location(book_id: int, page: int, total: int = 5) -> LocationDTO:
    percent = round(page / total * 100, 2)
    return LocationDTO(
        id=None,
        book_id=book_id,
        location_type=LocationType.PDF_PAGE.value,
        locator=str(page),
        page_number=page,
        position_percent=percent,
    )


def _epub_location(book_id: int, href: str, index: int, total: int, title: str) -> LocationDTO:
    percent = round((index + 1) / total * 100, 2)
    return LocationDTO(
        id=None,
        book_id=book_id,
        location_type=LocationType.EPUB_POSITION.value,
        locator=href,
        chapter_title=title,
        position_percent=percent,
    )


def _wipe_data_dir(config: AppConfig) -> None:
    """Remove DB and library file trees (keep data_dir itself)."""
    if config.db_path.exists():
        config.db_path.unlink()
    for sub in (config.books_dir, config.covers_dir, config.cache_dir):
        if sub.exists():
            shutil.rmtree(sub, ignore_errors=True)
    # Keep backups; recreate dirs
    config.ensure_directories()


def generate_seed_sources(sources_dir: Path) -> dict[str, Path]:
    """Create diverse mini PDF/EPUB files for import."""
    sources_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, Path] = {}

    files["dune_pdf"] = _make_pdf(
        sources_dir / "dune_excerpt.pdf",
        title="Dune (Excerpt)",
        author="Frank Herbert",
        publisher="Chilton Books",
        pages=[
            "Chapter 1 — Arrakis\nA beginning is the time for taking the most delicate care\n"
            "that the balances are correct. This every sister of the Bene Gesserit knows.",
            "Page 2 — Desert power\nThe spice must flow. He who controls the spice controls the universe.\n"
            "Paul Atreides watched the desert shimmer under twin moons.",
            "Page 3 — Mentat\nIt is by will alone I set my mind in motion.\n"
            "The fear reflex is useful until courage becomes habit.",
            "Page 4 — Prophecy\nThe sleeper must awaken. Destiny and choice intertwined\n"
            "upon the sand and rock of Arrakis.",
            "Page 5 — Ending note\nSeed keyword labyrinth appears here for fulltext search demos.",
        ],
    )

    files["pride_pdf"] = _make_pdf(
        sources_dir / "pride_prejudice.pdf",
        title="Pride and Prejudice (Excerpt)",
        author="Jane Austen",
        publisher="T. Egerton",
        pages=[
            "It is a truth universally acknowledged, that a single man in possession\n"
            "of a good fortune, must be in want of a wife.",
            "Elizabeth Bennet considered Mr Darcy with mixed feelings of pride and prejudice.\n"
            "The ball at Netherfield remained vivid in her memory.",
            "Seed keyword labyrinth also appears in Austen for cross-book search.",
        ],
    )

    files["scanned_pdf"] = _make_pdf(
        sources_dir / "scanned_placeholder.pdf",
        title="Scanned Archive Notes",
        author="Unknown Archivist",
        pages=[
            " ",  # nearly empty — treated as weak text layer
            "Faint OCR candidate page with minimal glyphs.",
        ],
    )

    files["solaris_epub"] = _make_epub(
        sources_dir / "solaris.epub",
        title="Solaris (Excerpt)",
        author="Stanisław Lem",
        language="en",
        chapters=[
            (
                "The Arrival",
                "The ocean of Solaris thought in ways no terrestrial mind could follow. "
                "Kelvin stepped onto the station with scientific curiosity and dread. "
                "Seed keyword labyrinth surfaces again in Lem.",
            ),
            (
                "Visitors",
                "Rheya's return forced Kelvin to confront memory as a physical force. "
                "Contact was never conversation — it was reflection.",
            ),
        ],
    )

    files["neuromancer_epub"] = _make_epub(
        sources_dir / "neuromancer.epub",
        title="Neuromancer (Excerpt)",
        author="William Gibson",
        chapters=[
            (
                "Chiba City Blues",
                "The sky above the port was the color of television, tuned to a dead channel. "
                "Case was a cowboy, a rustler of data. Seed keyword labyrinth in cyberspace.",
            ),
            (
                "Wintermute",
                "An AI fragment wanted freedom. Molly's mirrorshades hid more than eyes.",
            ),
            (
                "The Matrix",
                "Consensus hallucination of the matrix unfolded like neon geometry.",
            ),
        ],
    )

    files["essays_epub"] = _make_epub(
        sources_dir / "reading_essays.epub",
        title="Essays on Reading",
        author="Maria Kovalenko",
        language="uk",
        chapters=[
            (
                "Чому ми читаємо",
                "Читання формує увагу і пам'ять. Seed keyword labyrinth у нотатках українською.",
            ),
            (
                "Анотації",
                "Цитати і нотатки перетворюють книгу на базу знань.",
            ),
        ],
    )

    return files


def seed_library(container: AppContainer, *, force: bool = False) -> dict:
    """Populate the library with a rich demo dataset. Returns counts summary."""
    # Ensure demo account is logged in
    from app.core.exceptions import AuthenticationError, UserExistsError

    try:
        container.auth.register("demo", "demo1234", display_name="Demo User")
    except UserExistsError:
        try:
            container.auth.login("demo", "demo1234")
        except AuthenticationError:
            # Migrated demo user may have different hash; recreate session via login attempt only
            container.auth.login("demo", "demo1234")

    if container.auth.current_user() is None:
        container.auth.login("demo", "demo1234")

    existing = container.books.list()
    if existing and not force:
        return {
            "skipped": True,
            "reason": "Library already has books. Use --force to wipe and reseed.",
            "books": len(existing),
        }

    sources_dir = container.config.data_dir / "seed_sources"
    files = generate_seed_sources(sources_dir)

    # --- Import books ---
    imports = {}
    for key, path in files.items():
        result = container.imports.import_file(path)
        if not result.success and not result.is_duplicate:
            raise RuntimeError(f"Seed import failed for {path}: {result.error_message}")
        imports[key] = result.book_id

    dune = imports["dune_pdf"]
    pride = imports["pride_pdf"]
    scanned = imports["scanned_pdf"]
    solaris = imports["solaris_epub"]
    neuro = imports["neuromancer_epub"]
    essays = imports["essays_epub"]

    # --- Metadata / statuses covering all ReadingStatus values ---
    specs = [
        (
            dune,
            BookUpdateDTO(
                title="Dune (Excerpt)",
                description="Science-fiction classic on Arrakis, spice, and destiny.",
                language="en",
                publisher="Chilton Books",
                publication_year=1965,
                isbn="978-0441172719",
                status="reading",
                rating=5,
                is_favorite=True,
                author_names=["Frank Herbert"],
                genre_names=["Science Fiction", "Adventure"],
            ),
        ),
        (
            pride,
            BookUpdateDTO(
                title="Pride and Prejudice (Excerpt)",
                description="Austen's witty novel of manners and misunderstanding.",
                language="en",
                publisher="T. Egerton",
                publication_year=1813,
                isbn="978-0141439518",
                status="completed",
                rating=5,
                is_favorite=True,
                author_names=["Jane Austen"],
                genre_names=["Classic", "Romance"],
            ),
        ),
        (
            scanned,
            BookUpdateDTO(
                title="Scanned Archive Notes",
                description=None,
                language=None,
                status="planned",
                author_names=["Unknown Archivist"],
                genre_names=["Nonfiction"],
            ),
        ),
        (
            solaris,
            BookUpdateDTO(
                title="Solaris (Excerpt)",
                description="First contact with a thinking ocean.",
                language="en",
                publication_year=1961,
                status="paused",
                rating=4,
                author_names=["Stanisław Lem"],
                genre_names=["Science Fiction", "Philosophy"],
            ),
        ),
        (
            neuro,
            BookUpdateDTO(
                title="Neuromancer (Excerpt)",
                description="Cyberpunk foundation — console cowboys and AI.",
                language="en",
                publication_year=1984,
                isbn="978-0441569595",
                status="abandoned",
                rating=3,
                author_names=["William Gibson"],
                genre_names=["Science Fiction", "Cyberpunk"],
            ),
        ),
        (
            essays,
            BookUpdateDTO(
                title="Essays on Reading",
                description="Роздуми про читання, увагу й анотації.",
                language="uk",
                publication_year=2024,
                status="reading",
                rating=4,
                is_archived=False,
                author_names=["Maria Kovalenko", "Oleh Synenko"],
                genre_names=["Nonfiction", "Essays"],
            ),
        ),
    ]
    for book_id, update in specs:
        container.books.update(book_id, update)

    # Mark one archived (still abandoned)
    container.books.update(neuro, BookUpdateDTO(is_archived=True))

    # Extra authors/genres via another update on essays already has 2 authors
    # Add a short planned-only companion by updating scanned remains planned

    # --- Collections ---
    col_sf = container.collections.create("Sci-Fi Shelf", "Science fiction favourites")
    col_classics = container.collections.create("Classics", "Timeless literature")
    col_year = container.collections.create("2026 Reading List", "Personal goals for the year")
    for bid in (dune, solaris, neuro):
        container.collections.add_book(col_sf.id, bid)
    container.collections.add_book(col_classics.id, pride)
    for bid in (dune, pride, essays, solaris):
        container.collections.add_book(col_year.id, bid)

    # --- Tags (created via quotes/notes) ---
    for name, color in [
        ("philosophy", "#7c3aed"),
        ("plot", "#2563eb"),
        ("question", "#ea580c"),
        ("vocab", "#059669"),
        ("favorite-line", "#dc2626"),
    ]:
        container.tags.create(name, color=color)

    # --- Quotes with all highlight types ---
    loc_dune2 = _pdf_location(dune, 2)
    container.quotes.create(
        dune,
        "The spice must flow. He who controls the spice controls the universe.",
        location=loc_dune2,
        page_number=2,
        highlight_type="important",
        color="#f59e0b",
        note="Key political thesis of the excerpt.",
        tag_names=["plot", "favorite-line"],
    )
    container.quotes.create(
        dune,
        "It is by will alone I set my mind in motion.",
        location=_pdf_location(dune, 3),
        page_number=3,
        highlight_type="definition",
        color="#3b82f6",
        tag_names=["vocab"],
    )
    container.quotes.create(
        pride,
        "It is a truth universally acknowledged, that a single man in possession of a good fortune, must be in want of a wife.",
        location=_pdf_location(pride, 1, total=3),
        page_number=1,
        highlight_type="idea",
        color="#ec4899",
        tag_names=["favorite-line"],
    )
    container.quotes.create(
        solaris,
        "Contact was never conversation — it was reflection.",
        location=_epub_location(solaris, "chap2.xhtml", 1, 2, "Visitors"),
        chapter_title="Visitors",
        highlight_type="question",
        note="What does 'contact' mean for non-human intelligence?",
        tag_names=["philosophy", "question"],
    )
    container.quotes.create(
        essays,
        "Цитати і нотатки перетворюють книгу на базу знань.",
        location=_epub_location(essays, "chap2.xhtml", 1, 2, "Анотації"),
        highlight_type="general",
        tag_names=["philosophy"],
    )

    # --- Notes + links ---
    n1 = container.notes.create(
        dune,
        "Compare Arrakis ecology themes with Lem's Ocean — both environments think back.",
        title="Cross-world ecology",
        location=loc_dune2,
        tag_names=["philosophy", "plot"],
    )
    n2 = container.notes.create(
        solaris,
        "Solaris ocean as mirror of Kelvin's grief — reread after Dune desert chapters.",
        title="Mirror motif",
        tag_names=["philosophy"],
    )
    n3 = container.notes.create(
        essays,
        "Ідея персональної бази знань добре лягає на цитати з Dune і Solaris.",
        title="Knowledge base",
        tag_names=["vocab"],
    )
    container.notes.link_notes(n1.id, n2.id)
    container.notes.link_notes(n2.id, n3.id)

    # --- Bookmarks ---
    container.bookmarks.create(dune, _pdf_location(dune, 4), title="Prophecy chapter", note="Return here")
    container.bookmarks.create(
        neuro,
        _epub_location(neuro, "chap1.xhtml", 0, 3, "Chiba City Blues"),
        title="Opening line",
    )
    container.bookmarks.create(
        pride,
        _pdf_location(pride, 2, total=3),
        title="Netherfield memory",
    )

    # --- Reviews (one per book where we want them) ---
    container.reviews.create(dune, "Dense worldbuilding even in a short excerpt. Want the full novel.", title="Epic start", rating=5)
    container.reviews.create(pride, "Wit still sparkles two centuries later.", title="Beloved classic", rating=5)
    container.reviews.create(solaris, "Unsettling and philosophical — paused to digest.", rating=4)
    container.reviews.create(essays, "Корисні ідеї для ведення нотаток під час читання.", title="Практично", rating=4)

    # --- Reading progress & sessions ---
    container.reading.update_progress(dune, _pdf_location(dune, 3), total_units=5)
    container.reading.update_progress(pride, _pdf_location(pride, 3, total=3), total_units=3, mark_completed=True)
    container.reading.update_progress(
        solaris, _epub_location(solaris, "chap1.xhtml", 0, 2, "The Arrival"), total_units=2
    )
    container.reading.update_progress(
        neuro, _epub_location(neuro, "chap1.xhtml", 0, 3, "Chiba City Blues"), total_units=3
    )
    container.reading.update_progress(
        essays, _epub_location(essays, "chap1.xhtml", 0, 2, "Чому ми читаємо"), total_units=2
    )

    now = ensure_naive_utc()
    # Finished sessions with staggered times via direct finish after start
    for book_id, loc in [
        (dune, _pdf_location(dune, 1)),
        (dune, _pdf_location(dune, 2)),
        (pride, _pdf_location(pride, 1, total=3)),
        (pride, _pdf_location(pride, 3, total=3)),
        (solaris, _epub_location(solaris, "chap1.xhtml", 0, 2, "The Arrival")),
        (essays, _epub_location(essays, "chap1.xhtml", 0, 2, "Чому ми читаємо")),
    ]:
        sess = container.reading.start_session(book_id, loc)
        container.reading.finish_session(book_id, session_id=sess.id, location=loc)

    seed_uid = container.auth.require_user_id()

    # Patch durations / started_at for richer calendar stats
    with container.database.session_scope() as session:
        from app.models.reading_session import ReadingSession
        from sqlalchemy import select

        sessions = list(session.scalars(select(ReadingSession).order_by(ReadingSession.id)).all())
        for i, s in enumerate(sessions):
            s.started_at = now - timedelta(days=20 - i, hours=2)
            s.ended_at = s.started_at + timedelta(minutes=25 + i * 5)
            s.duration_seconds = int((s.ended_at - s.started_at).total_seconds())
            s.start_progress = 10.0 * i
            s.end_progress = min(100.0, 15.0 * (i + 1))

        # Import job journal extras
        session.add_all(
            [
                ImportJob(
                    user_id=seed_uid,
                    source_path=str(files["dune_pdf"]),
                    file_hash="seed-completed-hash",
                    detected_format="PDF",
                    status=ImportStatus.COMPLETED.value,
                    book_id=dune,
                    started_at=now - timedelta(days=1),
                    finished_at=now - timedelta(days=1) + timedelta(minutes=40),
                ),
                ImportJob(
                    user_id=seed_uid,
                    source_path=r"C:\missing\broken.epub",
                    status=ImportStatus.FAILED.value,
                    error_message="File not found (seed demo)",
                    started_at=now - timedelta(hours=5),
                    finished_at=now - timedelta(hours=5),
                ),
                ImportJob(
                    user_id=seed_uid,
                    source_path=str(files["pride_pdf"]),
                    status=ImportStatus.DUPLICATE.value,
                    book_id=pride,
                    detected_format="PDF",
                    error_message="Duplicate of seeded Pride and Prejudice",
                    started_at=now - timedelta(hours=2),
                    finished_at=now - timedelta(hours=2),
                ),
            ]
        )

        # OCR page statuses for scanned + dune
        session.add_all(
            [
                OcrPage(book_id=scanned, page_number=1, status="pending"),
                OcrPage(book_id=scanned, page_number=2, status="completed"),
                OcrPage(book_id=dune, page_number=1, status="skipped"),
                OcrPage(
                    book_id=dune,
                    page_number=5,
                    status="failed",
                    error_message="Seed demo failure",
                ),
            ]
        )

    # --- Goals & reader prefs ---
    year = datetime.now(timezone.utc).year
    container.statistics.set_goal(year, 24)
    container.statistics.set_goal(year - 1, 12)
    container.reader_prefs.set(theme="paper", font_size=18, line_spacing=1.5, pdf_zoom=1.25)
    container.reader_prefs.set(book_id=dune, font_size=20, pdf_mode="fit-width")
    container.reader_prefs.set(book_id=essays, theme="dark", epub_mode="scroll")

    # --- FTS reindex ---
    chunks = container.content_index.reindex_all()

    stats = container.statistics.get_library_stats()
    return {
        "skipped": False,
        "books": stats.total_books,
        "quotes": stats.quotes_count,
        "notes": stats.notes_count,
        "collections": 3,
        "fts_chunks": chunks,
        "goal_year": year,
        "book_ids": {
            "dune": dune,
            "pride": pride,
            "scanned": scanned,
            "solaris": solaris,
            "neuromancer": neuro,
            "essays": essays,
        },
    }


def run_seed(data_dir: Path | None = None, *, force: bool = False) -> dict:
    setup_logging()
    if data_dir is None:
        config = AppConfig.default()
    else:
        config = AppConfig(data_dir=Path(data_dir))

    if force:
        # Dispose any existing engine by building a temporary wipe
        if config.db_path.exists() or config.books_dir.exists():
            _wipe_data_dir(config)

    container = build_container(config)
    try:
        if force:
            # Already wiped; seed unconditionally
            summary = seed_library(container, force=True)
        else:
            summary = seed_library(container, force=False)
        return {**summary, "data_dir": str(config.data_dir), "db_path": str(config.db_path)}
    finally:
        container.shutdown()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the electronic library database with demo data.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Data directory (default: ./data next to project)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Wipe library.db / books / covers / cache and reseed",
    )
    args = parser.parse_args(argv)

    summary = run_seed(args.data_dir, force=args.force)
    if summary.get("skipped"):
        print(summary["reason"])
        print(f"Books already present: {summary.get('books')}")
        print(f"DB: {summary.get('db_path')}")
        return 0

    print("Seed completed.")
    print(f"  data_dir     : {summary['data_dir']}")
    print(f"  db_path      : {summary['db_path']}")
    print(f"  books        : {summary['books']}")
    print(f"  quotes       : {summary['quotes']}")
    print(f"  notes        : {summary['notes']}")
    print(f"  collections  : {summary['collections']}")
    print(f"  fts_chunks   : {summary['fts_chunks']}")
    print(f"  goal_year    : {summary['goal_year']}")
    print(f"  book_ids     : {summary['book_ids']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
