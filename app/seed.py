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
import textwrap
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
    font_candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    ]
    font_path = next((candidate for candidate in font_candidates if candidate.is_file()), None)
    if font_path is None:
        raise RuntimeError("A Unicode font is required to generate Ukrainian demo PDFs")
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        # Multi-line text
        y = 72
        for source_line in text.split("\n"):
            for line in textwrap.wrap(source_line, width=70) or [""]:
                page.insert_text(
                    (72, y),
                    line,
                    fontname="seed-ukrainian",
                    fontfile=str(font_path),
                )
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
    language: str = "uk",
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
    """Create complete original Ukrainian demo books for import."""
    sources_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, Path] = {}

    files["dune_pdf"] = _make_pdf(
        sources_dir / "mist_nad_tumanom.pdf",
        title="Місто над туманом",
        author="Олена Верес",
        publisher="Навчальне видання",
        pages=[
            "Розділ 1. Останній трамвай\nУ місті над рікою туман приходив раніше за вечір.\n"
            "Марта затрималася в архіві й почула дзвін останнього трамвая.",
            "Розділ 2. Квиток без дати\nНа сидінні лежав синій квиток без номера.\n"
            "На звороті хтось написав: «Шукай світло біля старого мосту».",
            "Розділ 3. Архіварка\nБіля мосту Марта зустріла пані Лідію, колишню архіварку.\n"
            "Та пояснила, що місто зберігає пам'ять у людських історіях.",
            "Розділ 4. Вікно на пагорбі\nРазом вони знайшли будинок із незачиненим вікном.\n"
            "Усередині лежали листи мешканців, які колись урятували район.",
            "Розділ 5. Ранок\nМарта передала листи до міського музею.\n"
            "Коли туман розвіявся, старий трамвай знову задзвонив на мосту.\n"
            "Тепер його маршрут був позначений на новій мапі міста.",
        ],
    )

    files["pride_pdf"] = _make_pdf(
        sources_dir / "lyst_z_horyshcha.pdf",
        title="Лист із зеленого горища",
        author="Марко Левченко",
        publisher="Навчальне видання",
        pages=[
            "Розділ 1. Ключ\nПісля ремонту бабусиної оселі Назар знайшов старий ключ.\n"
            "На бирці було написано: «Зелене горище. Для тих, хто пам'ятає».",
            "Розділ 2. Лист\nЗа маленькими дверцятами чекала коробка листів.\n"
            "Бабуся писала їх собі юній і берегла мрії, яких не встигла здійснити.",
            "Розділ 3. Відповідь\nНазар допоміг бабусі відкрити майстерню в старій оранжереї.\n"
            "Увечері вони написали лист уже не в минуле, а наступному поколінню.",
        ],
    )

    files["scanned_pdf"] = _make_pdf(
        sources_dir / "arkhiv_mandrivnyka.pdf",
        title="Архів мандрівника",
        author="Данило Струм",
        pages=[" ", "Сторінка щоденника. Подорожній залишив карту біля криниці."],
    )

    files["solaris_epub"] = _make_epub(
        sources_dir / "more_shcho_pamyataye.epub",
        title="Море, що пам'ятало",
        author="Ірина Лісова",
        chapters=[
            (
                "Берегова станція",
                "Дослідниця Соломія приїхала до маяка після шторму. Море принесло на берег "
                "дерев'яну скриньку з листами, написаними її власним почерком. Вона вирішила "
                "залишитися на ніч і перевірити, звідки взялися ці послання.",
            ),
            (
                "Голос у мушлі",
                "У найстарішій мушлі Соломія почула слова батька, якого давно не було поруч. "
                "Вона зрозуміла: море не відтворює людей, а повертає те, про що ми боялися "
                "поговорити. Дослідниця записала спогад і відпустила мушлю у воду.",
            ),
            (
                "Світло",
                "Перед світанком шторм ущух. Соломія залишила на березі відповідь для батька "
                "і ввімкнула маяк. Удень вона повезла скриньку до музею, де листи стали "
                "частиною виставки про пам'ять приморського містечка.",
            ),
        ],
    )

    files["neuromancer_epub"] = _make_epub(
        sources_dir / "svitlo_u_tramvayi.epub",
        title="Світло у старому трамваї",
        author="Тарас Мирний",
        chapters=[
            (
                "Несправний маршрут",
                "Інженер Остап отримав завдання відновити старий трамвайний маршрут. У вагоні "
                "він знайшов ліхтар, який спалахував щоразу, коли поруч хтось потребував допомоги. "
                "Остап вирішив перевірити його дивну властивість.",
            ),
            (
                "Нічний пасажир",
                "На першій зупинці до вагона зайшла дівчинка з порожнім кошиком. Вона шукала "
                "загубленого песика, а ліхтар освітив провулок біля парку. Остап вимкнув двигун "
                "і допоміг їй пройти темними алеями.",
            ),
            (
                "Повернення",
                "Песик чекав біля фонтану. Коли дівчинка обійняла його, ліхтар засвітився рівно. "
                "Остап повернувся до майстерні з думкою, що маршрут потрібен не лише місту, "
                "а й людям, які часом не знають, куди звернутися.",
            ),
        ],
    )

    files["essays_epub"] = _make_epub(
        sources_dir / "shchodennyk_chytacha.epub",
        title="Щоденник читача",
        author="Марія Коваленко",
        chapters=[
            (
                "Перша сторінка",
                "Читання вчить помічати деталі й ставити кращі запитання. Я почала записувати "
                "враження після кожного розділу, щоб повертатися до важливих думок і бачити, "
                "як змінюється моє ставлення до книжки.",
            ),
            (
                "Анотації",
                "Цитати допомагають зберегти точні слова, а нотатки — власну реакцію на них. "
                "Наприкінці місяця я перечитала записи й помітила спільну тему: улюблені герої "
                "не бояться змінювати думку. Тепер це моя маленька читацька традиція.",
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
                title="Місто над туманом",
                description="Завершена демоісторія про міські спогади та старий трамвай.",
                language="uk",
                publisher="Навчальне видання",
                publication_year=2025,
                status="reading",
                rating=5,
                is_favorite=True,
                author_names=["Олена Верес"],
                genre_names=["Міська проза", "Фантастика"],
            ),
        ),
        (
            pride,
            BookUpdateDTO(
                title="Лист із зеленого горища",
                description="Завершена демоісторія про родинну пам'ять і здійснені мрії.",
                language="uk",
                publisher="Навчальне видання",
                publication_year=2025,
                status="completed",
                rating=5,
                is_favorite=True,
                author_names=["Марко Левченко"],
                genre_names=["Сучасна проза", "Родинна історія"],
            ),
        ),
        (
            scanned,
            BookUpdateDTO(
                title="Архів мандрівника",
                description=None,
                language="uk",
                status="planned",
                author_names=["Данило Струм"],
                genre_names=["Пригоди"],
            ),
        ),
        (
            solaris,
            BookUpdateDTO(
                title="Море, що пам'ятало",
                description="Завершена історія про пам'ять, море та примирення.",
                language="uk",
                publication_year=2025,
                status="paused",
                rating=4,
                author_names=["Ірина Лісова"],
                genre_names=["Фантастика", "Психологічна проза"],
            ),
        ),
        (
            neuro,
            BookUpdateDTO(
                title="Світло у старому трамваї",
                description="Завершена пригодницька історія про взаємодопомогу в місті.",
                language="uk",
                publication_year=2025,
                status="abandoned",
                rating=3,
                author_names=["Тарас Мирний"],
                genre_names=["Пригоди", "Міська фантастика"],
            ),
        ),
        (
            essays,
            BookUpdateDTO(
                title="Щоденник читача",
                description="Невеликий практичний посібник про читацькі нотатки.",
                language="uk",
                publication_year=2024,
                status="reading",
                rating=4,
                is_archived=False,
                author_names=["Марія Коваленко", "Олег Синенко"],
                genre_names=["Нонфікшн", "Есеїстика"],
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
    col_sf = container.collections.create("Міські історії", "Оригінальні демокнижки про місто")
    col_classics = container.collections.create("Улюблене", "Книжки, до яких хочеться повертатися")
    col_year = container.collections.create("Читаю цього року", "Особистий читацький план")
    for bid in (dune, solaris, neuro):
        container.collections.add_book(col_sf.id, bid)
    container.collections.add_book(col_classics.id, pride)
    for bid in (dune, pride, essays, solaris):
        container.collections.add_book(col_year.id, bid)

    # --- Tags (created via quotes/notes) ---
    for name, color in [
        ("думка", "#7c3aed"),
        ("сюжет", "#2563eb"),
        ("запитання", "#ea580c"),
        ("словник", "#059669"),
        ("улюблене", "#dc2626"),
    ]:
        container.tags.create(name, color=color)

    # --- Quotes with all highlight types ---
    loc_dune2 = _pdf_location(dune, 2)
    container.quotes.create(
        dune,
        "Коли туман розвіявся, старий трамвай знову задзвонив на мосту.",
        location=loc_dune2,
        page_number=2,
        highlight_type="important",
        color="#f59e0b",
        note="Фінальний образ історії про збережену міську пам'ять.",
        tag_names=["сюжет", "улюблене"],
    )
    container.quotes.create(
        dune,
        "Місто зберігає пам'ять у людських історіях.",
        location=_pdf_location(dune, 3),
        page_number=3,
        highlight_type="definition",
        color="#3b82f6",
        tag_names=["словник"],
    )
    container.quotes.create(
        pride,
        "Мрії, яких не встигла здійснити.",
        location=_pdf_location(pride, 1, total=3),
        page_number=1,
        highlight_type="idea",
        color="#ec4899",
        tag_names=["улюблене"],
    )
    container.quotes.create(
        solaris,
        "Море не відтворює людей, а повертає те, про що ми боялися поговорити.",
        location=_epub_location(solaris, "chap2.xhtml", 1, 3, "Голос у мушлі"),
        chapter_title="Голос у мушлі",
        highlight_type="question",
        note="What does 'contact' mean for non-human intelligence?",
        tag_names=["думка", "запитання"],
    )
    container.quotes.create(
        essays,
        "Цитати і нотатки перетворюють книгу на базу знань.",
        location=_epub_location(essays, "chap2.xhtml", 1, 2, "Анотації"),
        highlight_type="general",
        tag_names=["думка"],
    )

    # --- Notes + links ---
    n1 = container.notes.create(
        dune,
        "Порівняти образи туману й моря: обидва середовища зберігають людську пам'ять.",
        title="Пам'ять міста і моря",
        location=loc_dune2,
        tag_names=["думка", "сюжет"],
    )
    n2 = container.notes.create(
        solaris,
        "Море повертає Соломії спогади, щоб вона змогла попрощатися.",
        title="Образ пам'яті",
        tag_names=["думка"],
    )
    n3 = container.notes.create(
        essays,
        "Окремі записи допомагають зібрати читацькі думки в особисту базу знань.",
        title="Моя читацька база",
        tag_names=["словник"],
    )
    container.notes.link_notes(n1.id, n2.id)
    container.notes.link_notes(n2.id, n3.id)

    # --- Bookmarks ---
    container.bookmarks.create(dune, _pdf_location(dune, 4), title="Вікно на пагорбі", note="Повернутися до листів")
    container.bookmarks.create(
        neuro,
        _epub_location(neuro, "chap1.xhtml", 0, 3, "Несправний маршрут"),
        title="Початок історії",
    )
    container.bookmarks.create(
        pride,
        _pdf_location(pride, 2, total=3),
        title="Коробка листів",
    )

    # --- Reviews (one per book where we want them) ---
    container.reviews.create(dune, "Тепла міська історія про те, як особисті спогади можуть зберегти цілий район.", title="Атмосферний початок", rating=5)
    container.reviews.create(pride, "Зворушлива історія про родинні листи та сміливість здійснити давню мрію.", title="Лист із минулого", rating=5)
    container.reviews.create(solaris, "Спокійна оповідь про пам'ять і прощання. Фінал залишає світле відчуття.", rating=4)
    container.reviews.create(essays, "Корисні ідеї для ведення нотаток під час читання.", title="Практично", rating=4)

    # --- Reading progress & sessions ---
    container.reading.update_progress(dune, _pdf_location(dune, 3), total_units=5)
    container.reading.update_progress(pride, _pdf_location(pride, 3, total=3), total_units=3, mark_completed=True)
    container.reading.update_progress(
        solaris, _epub_location(solaris, "chap1.xhtml", 0, 3, "Берегова станція"), total_units=3
    )
    container.reading.update_progress(
        neuro, _epub_location(neuro, "chap1.xhtml", 0, 3, "Несправний маршрут"), total_units=3
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
                    error_message="Дублікат демокнижки «Лист із зеленого горища»",
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
