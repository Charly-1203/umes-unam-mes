"""Course reset: leave the system clean for the next generation of students.

A reset always makes a backup first, then deletes data in one transaction according to the
chosen level, and records the action in the audit log. Stations (the physical equipment of the
laboratory), administrators and the audit log itself are never deleted.
"""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from sqlalchemy import Engine, delete
from sqlmodel import Session, SQLModel, func, select

from mes_core.enums import Role
from mes_core.permissions import Permission
from mes_server.db.engine import session_scope
from mes_server.db.models import (
    BomItem,
    DowntimeEvent,
    DowntimeReason,
    ExecutionRecord,
    Product,
    Recipe,
    RecipeStep,
    Unit,
    User,
    WorkOrder,
)
from mes_server.services import audit, backups
from mes_server.services.errors import ValidationError
from mes_server.services.validation import require_permission

CONFIRMATION_WORD = "REINICIAR"
"""Word the user must type to confirm a reset."""


class ResetLevel(StrEnum):
    """How much a course reset deletes. Each level includes the previous ones."""

    PRODUCTION = "production"
    """Work orders, units, execution records and downtime events."""

    CATALOGS = "catalogs"
    """Also products with their bills of materials, recipes and downtime reasons."""

    EVERYTHING = "everything"
    """Also every user that is not an administrator."""


_PRODUCTION: tuple[type[SQLModel], ...] = (ExecutionRecord, DowntimeEvent, Unit, WorkOrder)
_CATALOGS: tuple[type[SQLModel], ...] = (
    RecipeStep,
    Recipe,
    BomItem,
    Product,
    DowntimeReason,
)

LEVEL_TABLES: dict[ResetLevel, tuple[type[SQLModel], ...]] = {
    ResetLevel.PRODUCTION: _PRODUCTION,
    ResetLevel.CATALOGS: _PRODUCTION + _CATALOGS,
    ResetLevel.EVERYTHING: _PRODUCTION + _CATALOGS,
}
"""Tables emptied by each level, in an order that respects foreign keys."""


@dataclass(frozen=True, slots=True)
class ResetResult:
    """Outcome of a course reset.

    Attributes:
        level: Level applied.
        deleted: Rows deleted per table.
        backup: Backup made before deleting.
    """

    level: ResetLevel
    deleted: dict[str, int]
    backup: backups.BackupInfo


def preview(session: Session, level: ResetLevel) -> dict[str, int]:
    """Count the rows a reset would delete, without deleting anything.

    Args:
        session: Open database session.
        level: Level to preview.

    Returns:
        Rows per table that the level would delete.
    """
    counts = {
        model.__tablename__: session.exec(select(func.count()).select_from(model)).one()  # type: ignore[attr-defined]
        for model in LEVEL_TABLES[level]
    }
    if level is ResetLevel.EVERYTHING:
        counts[User.__tablename__] = session.exec(
            select(func.count()).select_from(User).where(User.role != Role.ADMIN)
        ).one()
    return counts


def _delete(session: Session, level: ResetLevel) -> dict[str, int]:
    deleted: dict[str, int] = {}
    for model in LEVEL_TABLES[level]:
        result = session.exec(delete(model))  # type: ignore[call-overload]
        deleted[model.__tablename__] = result.rowcount  # type: ignore[attr-defined]
    if level is ResetLevel.EVERYTHING:
        result = session.exec(delete(User).where(User.role != Role.ADMIN))  # type: ignore[call-overload]
        deleted[User.__tablename__] = result.rowcount
    return deleted


def reset_course(
    engine: Engine,
    database_url: str,
    backup_dir: Path,
    level: ResetLevel,
    *,
    actor: str,
    actor_role: Role,
    confirmation: str,
) -> ResetResult:
    """Back up the database and delete the data of a course.

    Args:
        engine: Database engine.
        database_url: SQLAlchemy URL of the same database, used for the backup.
        backup_dir: Folder for backups.
        level: How much to delete.
        actor: Username of who asks for the reset, or ``"terminal"``.
        actor_role: Role of who asks for the reset.
        confirmation: Text typed by the user; it must be :data:`CONFIRMATION_WORD`.

    Returns:
        What was deleted and the backup that was made.

    Raises:
        PermissionDeniedError: If the role is not an administrator.
        ValidationError: If the confirmation word does not match.
        BackupError: If the backup fails; in that case nothing is deleted.
    """
    require_permission(actor_role, Permission.ADMINISTER_SYSTEM)
    if confirmation.strip() != CONFIRMATION_WORD:
        raise ValidationError(
            "Confirmation word does not match.", code="confirmation", field="confirmation"
        )

    backup = backups.create_backup(
        database_url, backup_dir, created_by=actor, reason=f"course-reset-{level.value}"
    )
    with session_scope(engine) as session:
        deleted = _delete(session, level)
        audit.record(
            session,
            actor=actor,
            action="course_reset",
            detail={"level": level.value, "deleted": deleted, "backup": backup.file_name},
        )
    return ResetResult(level=level, deleted=deleted, backup=backup)


def backup_now(
    engine: Engine, database_url: str, backup_dir: Path, *, actor: str, actor_role: Role
) -> backups.BackupInfo:
    """Make a manual backup and record it in the audit log.

    Args:
        engine: Database engine.
        database_url: SQLAlchemy URL of the same database.
        backup_dir: Folder for backups.
        actor: Username of who asks for the backup, or ``"terminal"``.
        actor_role: Role of who asks for the backup.

    Returns:
        The new backup.

    Raises:
        PermissionDeniedError: If the role is not an administrator.
        BackupError: If the backup fails.
    """
    require_permission(actor_role, Permission.ADMINISTER_SYSTEM)
    backup = backups.create_backup(database_url, backup_dir, created_by=actor)
    with session_scope(engine) as session:
        audit.record(
            session, actor=actor, action="backup_created", detail={"backup": backup.file_name}
        )
    return backup
