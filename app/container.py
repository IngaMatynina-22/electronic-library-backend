"""Dependency injection container for the library backend."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import AppConfig
from app.core.database import Database
from app.services.auth_service import AuthService
from app.services.backup_service import BackupService
from app.services.book_service import BookService
from app.services.bookmark_service import BookmarkService
from app.services.collection_service import CollectionService
from app.services.content_index_service import ContentIndexService
from app.services.export_service import ExportService
from app.services.import_service import ImportService
from app.services.library_org_service import LibraryOrgService
from app.services.note_service import NoteService
from app.services.ocr_service import OcrService
from app.services.quote_service import QuoteService
from app.services.reader_prefs_service import ReaderPrefsService
from app.services.reader_service import ReaderService
from app.services.reading_service import ReadingService
from app.services.review_service import ReviewService
from app.services.search_service import SearchService
from app.services.statistics_service import StatisticsService
from app.services.tag_service import TagService
from app.storage.cache_manager import CacheManager
from app.storage.cover_manager import CoverManager
from app.storage.file_manager import FileManager
from app.storage.path_resolver import PathResolver


@dataclass
class AppContainer:
    """Holds configured services for the GUI layer."""

    config: AppConfig
    database: Database
    path_resolver: PathResolver
    file_manager: FileManager
    cover_manager: CoverManager
    cache_manager: CacheManager
    content_index: ContentIndexService
    auth: AuthService
    books: BookService
    imports: ImportService
    reader: ReaderService
    reading: ReadingService
    quotes: QuoteService
    bookmarks: BookmarkService
    notes: NoteService
    reviews: ReviewService
    collections: CollectionService
    search: SearchService
    statistics: StatisticsService
    backup: BackupService
    tags: TagService
    export: ExportService
    library_org: LibraryOrgService
    ocr: OcrService
    reader_prefs: ReaderPrefsService

    def shutdown(self) -> None:
        self.database.dispose()


def build_container(config: AppConfig) -> AppContainer:
    config.ensure_directories()
    database = Database(config)
    database.create_tables()

    path_resolver = PathResolver(config)
    file_manager = FileManager(config, path_resolver)
    cover_manager = CoverManager(config, path_resolver)
    cache_manager = CacheManager(config, path_resolver)
    content_index = ContentIndexService(database, path_resolver)
    auth = AuthService(database, config)

    reading = ReadingService(database, auth)
    tags = TagService(database, auth)
    books = BookService(
        database, file_manager, cache_manager, content_index, auth, cover_manager
    )
    imports = ImportService(
        database, file_manager, cover_manager, path_resolver, content_index, auth
    )
    reader = ReaderService(database, path_resolver, reading, auth)
    quotes = QuoteService(database, content_index, tags, auth)
    bookmarks = BookmarkService(database, auth)
    notes = NoteService(database, content_index, tags, auth)
    reviews = ReviewService(database, auth)
    collections = CollectionService(database, auth)
    search = SearchService(database, auth)
    statistics = StatisticsService(database, auth)
    backup = BackupService(database, config, path_resolver)
    export = ExportService(database, auth)
    library_org = LibraryOrgService(database, auth)
    ocr = OcrService(database, path_resolver, content_index, auth)
    reader_prefs = ReaderPrefsService(database, auth)

    return AppContainer(
        config=config,
        database=database,
        path_resolver=path_resolver,
        file_manager=file_manager,
        cover_manager=cover_manager,
        cache_manager=cache_manager,
        content_index=content_index,
        auth=auth,
        books=books,
        imports=imports,
        reader=reader,
        reading=reading,
        quotes=quotes,
        bookmarks=bookmarks,
        notes=notes,
        reviews=reviews,
        collections=collections,
        search=search,
        statistics=statistics,
        backup=backup,
        tags=tags,
        export=export,
        library_org=library_org,
        ocr=ocr,
        reader_prefs=reader_prefs,
    )
