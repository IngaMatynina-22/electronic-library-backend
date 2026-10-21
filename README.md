# Персональна електронна бібліотека — Python-бекенд

Локальний бекенд для настільного застосунку на PySide6. Без REST API, JWT і окремого сервера: GUI викликає Python-сервіси напряму.

## Можливості

- Імпорт PDF (PyMuPDF) та EPUB (EbookLib) з метаданими, обкладинками та виявленням дублікатів (SHA-256)
- CRUD книг, авторів, жанрів і колекцій
- Вбудований читач із збереженням позиції та прогресу
- Сесії читання, закладки, цитати, нотатки та відгуки
- Пошук, фільтрація, сортування та статистика
- Резервне копіювання / відновлення SQLite (+ файли)
- **FTS5** повнотекстовий пошук по вмісту книг, цитатах і нотатках (`search.search_fulltext`)
- Теги, типи виділень, зв’язки нотаток, експорт у Markdown/JSON
- Читацькі цілі та розширена аналітика / календар активності
- Розумна організація: дублікати, bulk-edit, CSV/JSON метаданих, схожі книги
- Профілі відображення читача (global + per-book)
- OCR для сканованих PDF (опційно, потрібен Tesseract)

## Встановлення

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Для OCR додатково встановіть [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) у системі.

## Локальні акаунти

Без REST/JWT: реєстрація і вхід у SQLite, ізоляція бібліотеки по `user_id`.

```python
from app.main import init_backend

container = init_backend()
container.auth.register("alice", "secret12")   # або login("alice", "secret12")
# далі всі сервіси працюють у контексті поточного користувача
container.auth.logout()
```

Seed створює користувача `demo` / `demo1234`.

## Ініціалізація з GUI

```python
from app.main import init_backend

container = init_backend()
container.auth.login("demo", "demo1234")

result = container.imports.import_file(r"C:\books\novel.epub")
hits = container.search.search_fulltext("keyword")
container.quotes.create(result.book_id, "text", highlight_type="idea", tag_names=["key"])
container.export.export_knowledge("export.md", format="markdown")
container.statistics.set_goal(2026, 20)
container.reader_prefs.set(theme="paper", font_size=18)
```

Довгі імпорти / OCR варто запускати в `QThread` з `progress_callback`.

## Структура даних

```
data/
├── library.db
├── books/<uuid>/original.pdf|epub
├── covers/
├── cache/extracted_content/
└── backups/
```

## Архітектура

- **GUI** → `AppContainer` → **Services** → **Repositories** → **SQLAlchemy / SQLite**
- FTS5 індекси створюються в `ensure_extensions` після `create_all`
- OCR опційний: `container.ocr.is_available()`

## Seed демо-даних

Максимально повний набір книг, цитат, нотаток, сесій, цілей, тегів, колекцій тощо:

```bash
python -m app.seed
python -m app.seed --force
python -m app.seed --data-dir PATH --force
```

`--force` очищає `library.db`, `books/`, `covers/`, `cache/` і заповнює заново. Без `--force` скрипт не перезаписує вже наявну бібліотеку.

## Тести

```bash
pytest -q
```
