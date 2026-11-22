"""Catalog of reasons that explain why a station stopped."""

from sqlmodel import Session, select

from mes_core.enums import Role
from mes_server.db.models import DowntimeEvent, DowntimeReason
from mes_server.services import catalog
from mes_server.services.validation import normalize_code, required_text

REFERENCES = (catalog.Reference("downtime events", DowntimeEvent.reason_id),)
"""Records that point at a reason and therefore keep it from being deleted."""


def list_reasons(session: Session, *, include_inactive: bool = False) -> list[DowntimeReason]:
    """Return downtime reasons ordered by code.

    Args:
        session: Open database session.
        include_inactive: Also return deactivated reasons.

    Returns:
        The reasons.
    """
    statement = select(DowntimeReason).order_by(DowntimeReason.code)
    if not include_inactive:
        statement = statement.where(DowntimeReason.is_active == True)  # noqa: E712
    return list(session.exec(statement).all())


def get_reason(session: Session, reason_id: int) -> DowntimeReason:
    """Load a downtime reason.

    Args:
        session: Open database session.
        reason_id: Primary key.

    Returns:
        The reason.

    Raises:
        NotFoundError: If it does not exist.
    """
    return catalog.get_or_raise(session, DowntimeReason, reason_id)


def create_reason(session: Session, *, code: str, description: str) -> DowntimeReason:
    """Create a downtime reason.

    Args:
        session: Open database session. The caller commits.
        code: Unique short code, normalized to uppercase, such as ``"NO_MATERIAL"``.
        description: Text shown to the operator.

    Returns:
        The new reason.

    Raises:
        ValidationError: If a field breaks the rules.
        AlreadyExistsError: If the code is taken.
    """
    normalized = normalize_code(code, max_length=32)
    reason = DowntimeReason(
        code=normalized,
        description=required_text(description, field="description", max_length=256),
    )
    catalog.ensure_code_available(session, DowntimeReason, normalized)
    session.add(reason)
    session.flush()
    return reason


def update_reason(session: Session, reason_id: int, *, description: str) -> DowntimeReason:
    """Change a reason's description. The code never changes.

    Args:
        session: Open database session. The caller commits.
        reason_id: Primary key.
        description: New description.

    Returns:
        The updated reason.
    """
    reason = get_reason(session, reason_id)
    reason.description = required_text(description, field="description", max_length=256)
    session.add(reason)
    return reason


def set_reason_active(session: Session, reason_id: int, active: bool) -> DowntimeReason:
    """Activate or deactivate a reason.

    Args:
        session: Open database session. The caller commits.
        reason_id: Primary key.
        active: New state.

    Returns:
        The reason.
    """
    reason = get_reason(session, reason_id)
    catalog.set_active(reason, active)
    session.add(reason)
    return reason


def reason_usage(session: Session, reason_id: int) -> dict[str, int]:
    """Count the downtime events that use a reason.

    Args:
        session: Open database session.
        reason_id: Primary key.

    Returns:
        Non-zero counts keyed by reference label.
    """
    return catalog.count_references(session, reason_id, REFERENCES)


def delete_reason(session: Session, reason_id: int, *, actor_role: Role) -> None:
    """Delete a reason that no downtime event uses.

    Args:
        session: Open database session. The caller commits.
        reason_id: Primary key.
        actor_role: Role of the user asking for the deletion.

    Raises:
        NotFoundError: If it does not exist.
        PermissionDeniedError: If the role is not an administrator.
        InUseError: If downtime events use it.
    """
    reason = get_reason(session, reason_id)
    catalog.delete_unused(session, reason, reason_id, REFERENCES, actor_role=actor_role)
