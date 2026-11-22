"""Database backups.

A backup is a consistent copy of the SQLite database taken with SQLite's online backup API,
so it can be made while the server is running. Next to each copy a manifest (a JSON file with
the same name) records when and why it was made, who made it, the schema revision and how many
rows each table had.

Restoring from the application is not available yet. The manifest carries what a future restore
needs: the format version, the schema revision (to migrate an old copy forward with
``mes-server db upgrade``) and the row counts (to verify the result). Until then a copy is
restored by hand; see ``docs/adr/0009-respaldos-y-reinicio-de-curso.md``.
"""

import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlmodel import SQLModel

import mes_server.db.models  # noqa: F401  (registers every table)
from mes_core.clock import utc_now
from mes_server import __version__
from mes_server.db.engine import create_db_engine
from mes_server.db.migrate import current_revision
from mes_server.services.errors import ServiceError

MANIFEST_FORMAT = 1
"""Version of the manifest layout; increase it when its fields change."""

BACKUP_SUFFIX = ".db"
MANIFEST_SUFFIX = ".json"
DEFAULT_DIR_NAME = "respaldos"


class BackupError(ServiceError):
    """A backup could not be made or read."""

    code = "backup_failed"


@dataclass(frozen=True, slots=True)
class BackupInfo:
    """A backup and its manifest.

    Attributes:
        file_name: Name of the database copy, such as ``mes-20270615-180000.db``.
        path: Full path of the copy.
        size_bytes: Size of the copy.
        created_at: When it was made, in UTC.
        created_by: Username of who made it, or ``"terminal"``.
        reason: Why it was made, such as ``"manual"`` or ``"course_reset"``.
        schema_revision: Database schema revision of the copy.
        app_version: Version of ``mes-server`` that made it.
        row_counts: Rows per table at the moment of the copy.
    """

    file_name: str
    path: Path
    size_bytes: int
    created_at: datetime
    created_by: str
    reason: str
    schema_revision: str | None
    app_version: str
    row_counts: dict[str, int]


def sqlite_path(database_url: str) -> Path | None:
    """Return the file of a SQLite database, or ``None`` for other databases.

    Args:
        database_url: SQLAlchemy URL.

    Returns:
        The database file path, or ``None`` for in-memory or non-SQLite databases.
    """
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite" or url.database in (None, "", ":memory:"):
        return None
    return Path(url.database)


def default_backup_dir(database_url: str) -> Path | None:
    """Return the default backup folder: ``respaldos`` next to the database file.

    Args:
        database_url: SQLAlchemy URL.

    Returns:
        The folder, or ``None`` when the database is not a SQLite file.
    """
    path = sqlite_path(database_url)
    return None if path is None else path.parent / DEFAULT_DIR_NAME


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _row_counts(database_path: Path) -> dict[str, int]:
    engine = create_db_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        with engine.connect() as connection:
            return {
                name: connection.execute(select(func.count()).select_from(table)).scalar_one()
                for name, table in sorted(SQLModel.metadata.tables.items())
            }
    finally:
        engine.dispose()


def verify_backup(path: Path) -> None:
    """Check that a backup file is a healthy SQLite database.

    Args:
        path: Backup file.

    Raises:
        BackupError: If the file is missing or the integrity check fails.
    """
    if not path.is_file():
        raise BackupError(f"Backup {path} does not exist.")
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        result = connection.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.DatabaseError as error:
        raise BackupError(f"Backup {path} is not a valid database: {error}") from error
    finally:
        connection.close()
    if result is None or result[0] != "ok":
        raise BackupError(f"Backup {path} failed the integrity check: {result}")


def create_backup(
    database_url: str, backup_dir: Path, *, created_by: str, reason: str = "manual"
) -> BackupInfo:
    """Copy the database into ``backup_dir`` and write its manifest.

    The copy is written under a temporary name and renamed once complete and verified, so a
    failed backup never leaves a partial file that looks valid.

    Args:
        database_url: SQLAlchemy URL of the database to copy; it must be a SQLite file.
        backup_dir: Folder for backups; it is created if missing.
        created_by: Username of who asked for the backup, or ``"terminal"``.
        reason: Why the backup is made.

    Returns:
        The new backup.

    Raises:
        BackupError: If the database is not a SQLite file or the copy fails.
    """
    source = sqlite_path(database_url)
    if source is None or not source.is_file():
        raise BackupError("Backups are only available for SQLite database files.")

    backup_dir.mkdir(parents=True, exist_ok=True)
    created_at = utc_now()
    stem = f"mes-{created_at:%Y%m%d-%H%M%S}"
    if reason != "manual":
        stem += f"-{_slug(reason)}"
    target = backup_dir / f"{stem}{BACKUP_SUFFIX}"
    counter = 1
    while target.exists():
        counter += 1
        target = backup_dir / f"{stem}-{counter}{BACKUP_SUFFIX}"
    partial = target.with_suffix(".partial")

    source_connection = sqlite3.connect(source)
    target_connection = sqlite3.connect(partial)
    try:
        source_connection.backup(target_connection)
    except sqlite3.Error as error:
        target_connection.close()
        partial.unlink(missing_ok=True)
        raise BackupError(f"Could not copy the database: {error}") from error
    finally:
        source_connection.close()
    target_connection.close()

    try:
        verify_backup(partial)
    except BackupError:
        partial.unlink(missing_ok=True)
        raise
    partial.rename(target)

    info = BackupInfo(
        file_name=target.name,
        path=target,
        size_bytes=target.stat().st_size,
        created_at=created_at,
        created_by=created_by,
        reason=reason,
        schema_revision=current_revision(f"sqlite:///{target.as_posix()}"),
        app_version=__version__,
        row_counts=_row_counts(target),
    )
    _write_manifest(info)
    return info


def _write_manifest(info: BackupInfo) -> None:
    data = asdict(info)
    data.pop("path")
    data["format"] = MANIFEST_FORMAT
    data["created_at"] = info.created_at.isoformat()
    manifest = info.path.with_suffix(MANIFEST_SUFFIX)
    manifest.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _read_backup(path: Path) -> BackupInfo:
    manifest = path.with_suffix(MANIFEST_SUFFIX)
    data: dict = {}
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
    stat = path.stat()
    created_at = data.get("created_at")
    return BackupInfo(
        file_name=path.name,
        path=path,
        size_bytes=stat.st_size,
        created_at=(
            datetime.fromisoformat(created_at)
            if created_at
            else datetime.fromtimestamp(stat.st_mtime).astimezone()
        ),
        created_by=data.get("created_by", "desconocido"),
        reason=data.get("reason", "desconocido"),
        schema_revision=data.get("schema_revision"),
        app_version=data.get("app_version", "desconocido"),
        row_counts=data.get("row_counts", {}),
    )


def list_backups(backup_dir: Path) -> list[BackupInfo]:
    """Return the backups in a folder, newest first.

    Copies without a manifest (for example, copied by hand) are listed with the information
    that can be read from the file itself.

    Args:
        backup_dir: Folder for backups.

    Returns:
        The backups.
    """
    if not backup_dir.is_dir():
        return []
    backups = [_read_backup(path) for path in backup_dir.glob(f"*{BACKUP_SUFFIX}")]
    return sorted(backups, key=lambda backup: backup.created_at, reverse=True)


def find_backup(backup_dir: Path, file_name: str) -> BackupInfo:
    """Find a backup by file name, refusing names outside the folder.

    Args:
        backup_dir: Folder for backups.
        file_name: Name of the copy.

    Returns:
        The backup.

    Raises:
        BackupError: If the name is not a plain file name or the backup does not exist.
    """
    if Path(file_name).name != file_name or not file_name.endswith(BACKUP_SUFFIX):
        raise BackupError(f"Invalid backup name '{file_name}'.")
    path = backup_dir / file_name
    if not path.is_file():
        raise BackupError(f"Backup '{file_name}' does not exist.")
    return _read_backup(path)
