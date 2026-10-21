"""Backup and restore of the local library."""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import AppConfig
from app.core.database import Database
from app.core.exceptions import BackupError
from app.schemas.dtos import BackupResult
from app.storage.path_resolver import PathResolver

logger = logging.getLogger(__name__)

MANIFEST_NAME = "manifest.json"
DB_BACKUP_NAME = "library.db"


class BackupService:
    def __init__(
        self,
        database: Database,
        config: AppConfig,
        path_resolver: PathResolver,
    ) -> None:
        self.db = database
        self.config = config
        self.paths = path_resolver

    def create_backup(
        self,
        *,
        include_files: bool = True,
        destination: str | Path | None = None,
    ) -> BackupResult:
        self.config.ensure_directories()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        if destination is None:
            dest = self.config.backups_dir / f"library_backup_{stamp}.zip"
        else:
            dest = Path(destination)
            dest.parent.mkdir(parents=True, exist_ok=True)

        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                db_copy = tmp_path / DB_BACKUP_NAME
                self._sqlite_backup(self.config.db_path, db_copy)

                manifest = {
                    "version": 1,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "includes_files": include_files,
                    "db_file": DB_BACKUP_NAME,
                }
                (tmp_path / MANIFEST_NAME).write_text(
                    json.dumps(manifest, indent=2), encoding="utf-8"
                )

                with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                    zf.write(db_copy, DB_BACKUP_NAME)
                    zf.write(tmp_path / MANIFEST_NAME, MANIFEST_NAME)
                    if include_files:
                        self._add_tree(zf, self.config.books_dir, "books")
                        self._add_tree(zf, self.config.covers_dir, "covers")

            return BackupResult(
                success=True,
                path=str(dest),
                message="Backup created successfully",
                includes_files=include_files,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Backup failed")
            raise BackupError(f"Failed to create backup: {exc}") from exc

    def validate_backup(self, archive_path: str | Path) -> dict:
        path = Path(archive_path)
        if not path.is_file():
            raise BackupError(f"Backup file not found: {path}")
        try:
            with zipfile.ZipFile(path, "r") as zf:
                names = set(zf.namelist())
                if MANIFEST_NAME not in names:
                    raise BackupError("Backup archive is missing manifest.json")
                if DB_BACKUP_NAME not in names:
                    raise BackupError("Backup archive is missing library.db")
                manifest = json.loads(zf.read(MANIFEST_NAME).decode("utf-8"))
                # Quick SQLite integrity check on extracted DB
                with tempfile.TemporaryDirectory() as tmp:
                    db_path = Path(tmp) / DB_BACKUP_NAME
                    with zf.open(DB_BACKUP_NAME) as src, open(db_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    conn = sqlite3.connect(db_path)
                    try:
                        result = conn.execute("PRAGMA integrity_check").fetchone()
                        if not result or result[0] != "ok":
                            raise BackupError("Backup database failed integrity check")
                    finally:
                        conn.close()
                return {
                    "valid": True,
                    "manifest": manifest,
                    "files": sorted(names),
                }
        except BackupError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise BackupError(f"Invalid backup archive: {exc}") from exc

    def restore_backup(
        self,
        archive_path: str | Path,
        *,
        create_safety_backup: bool = True,
    ) -> BackupResult:
        info = self.validate_backup(archive_path)
        path = Path(archive_path)

        if create_safety_backup and self.config.db_path.exists():
            safety = self.create_backup(
                include_files=True,
                destination=self.config.backups_dir
                / f"pre_restore_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.zip",
            )
            logger.info("Safety backup created at %s", safety.path)

        self.db.dispose()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                with zipfile.ZipFile(path, "r") as zf:
                    zf.extractall(tmp_path)

                restored_db = tmp_path / DB_BACKUP_NAME
                if not restored_db.exists():
                    raise BackupError("Extracted backup is missing library.db")

                # Replace database
                if self.config.db_path.exists():
                    self.config.db_path.unlink()
                shutil.copy2(restored_db, self.config.db_path)

                includes_files = bool(info["manifest"].get("includes_files"))
                if includes_files:
                    self._restore_dir(tmp_path / "books", self.config.books_dir)
                    self._restore_dir(tmp_path / "covers", self.config.covers_dir)

            # Re-init engine against restored DB
            self.db.engine.dispose()
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker

            url = f"sqlite:///{self.config.db_path.as_posix()}"
            self.db.engine = create_engine(
                url, echo=False, connect_args={"check_same_thread": False}
            )
            Database._configure_sqlite(self.db.engine)
            self.db._session_factory = sessionmaker(
                bind=self.db.engine, autoflush=False, autocommit=False, expire_on_commit=False
            )

            return BackupResult(
                success=True,
                path=str(path),
                message="Backup restored successfully",
                includes_files=includes_files,
            )
        except BackupError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Restore failed")
            raise BackupError(f"Failed to restore backup: {exc}") from exc

    @staticmethod
    def _sqlite_backup(source: Path, destination: Path) -> None:
        if not source.exists():
            # Empty library — create empty db file placeholder
            destination.touch()
            return
        src = sqlite3.connect(source)
        try:
            dst = sqlite3.connect(destination)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()

    @staticmethod
    def _add_tree(zf: zipfile.ZipFile, directory: Path, arc_prefix: str) -> None:
        if not directory.exists():
            return
        for path in directory.rglob("*"):
            if path.is_file():
                arcname = f"{arc_prefix}/{path.relative_to(directory).as_posix()}"
                zf.write(path, arcname)

    @staticmethod
    def _restore_dir(src: Path, dest: Path) -> None:
        if not src.exists():
            return
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
