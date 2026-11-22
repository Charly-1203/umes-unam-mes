"""Audit log of administrative actions."""

from typing import Any

from sqlmodel import Session, select

from mes_server.db.models import AuditEntry

TERMINAL_ACTOR = "terminal"
"""Actor recorded for actions run from the command line."""


def record(session: Session, *, actor: str, action: str, detail: dict[str, Any]) -> AuditEntry:
    """Add an entry to the audit log.

    Args:
        session: Open database session. The caller commits.
        actor: Username of who performed the action, or :data:`TERMINAL_ACTOR`.
        action: Stable action identifier, such as ``"course_reset"``.
        detail: Additional data about the action; must be JSON serializable.

    Returns:
        The new entry.
    """
    entry = AuditEntry(actor=actor, action=action, detail=detail)
    session.add(entry)
    session.flush()
    return entry


def list_recent(session: Session, *, limit: int = 20) -> list[AuditEntry]:
    """Return the most recent entries, newest first.

    Args:
        session: Open database session.
        limit: Maximum number of entries.

    Returns:
        The entries.
    """
    statement = (
        select(AuditEntry).order_by(AuditEntry.created_at.desc(), AuditEntry.id.desc()).limit(limit)  # type: ignore[union-attr]
    )
    return list(session.exec(statement).all())
