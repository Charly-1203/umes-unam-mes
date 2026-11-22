"""Building blocks shared by the catalog services (products, stations, downtime reasons).

Catalog records follow the same rules:

* They are identified by a unique, uppercase ``code`` that never changes after creation.
* Anyone allowed to maintain them can deactivate and reactivate them. Inactive records stay in
  the history but are not offered for new work.
* Only an administrator can delete them, and only while nothing references them. Records with
  history are removed by the course reset, never one by one.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, SQLModel, func, select

from mes_core.enums import Role
from mes_core.permissions import Permission
from mes_server.services.errors import AlreadyExistsError, InUseError, NotFoundError
from mes_server.services.validation import require_permission


@dataclass(frozen=True, slots=True)
class Reference:
    """A column of another table that points at a catalog record.

    Attributes:
        label: What the referencing records are, in plural, for messages (``"recipes"``).
        column: Foreign key column, such as ``Recipe.product_id``.
    """

    label: str
    column: Any


def get_or_raise[M: SQLModel](session: Session, model: type[M], record_id: int) -> M:
    """Load a record by id.

    Args:
        session: Open database session.
        model: Table to read.
        record_id: Primary key.

    Returns:
        The record.

    Raises:
        NotFoundError: If no record has that id.
    """
    record = session.get(model, record_id)
    if record is None:
        raise NotFoundError(f"{model.__name__} {record_id} does not exist.")
    return record


def ensure_code_available(session: Session, model: type[SQLModel], code: str) -> None:
    """Check that no record of ``model`` uses ``code``.

    Args:
        session: Open database session.
        model: Table with a ``code`` column.
        code: Normalized code.

    Raises:
        AlreadyExistsError: If the code is taken.
    """
    existing = session.exec(select(model).where(model.code == code)).first()  # type: ignore[attr-defined]
    if existing is not None:
        raise AlreadyExistsError(f"{model.__name__} '{code}' already exists.", field="code")


def count_references(
    session: Session, record_id: int, references: Sequence[Reference]
) -> dict[str, int]:
    """Count the records that point at a catalog record.

    Args:
        session: Open database session.
        record_id: Primary key of the catalog record.
        references: Columns that may point at it.

    Returns:
        For each reference label, how many records point at the record; only non-zero counts.
    """
    counts: dict[str, int] = {}
    for reference in references:
        count = session.exec(
            select(func.count())
            .select_from(reference.column.table)
            .where(reference.column == record_id)
        ).one()
        if count:
            counts[reference.label] = count
    return counts


def set_active(record: SQLModel, active: bool) -> None:
    """Activate or deactivate a catalog record.

    Args:
        record: Record with an ``is_active`` field.
        active: New state.
    """
    record.is_active = active  # type: ignore[attr-defined]


def delete_unused(
    session: Session,
    record: SQLModel,
    record_id: int,
    references: Sequence[Reference],
    *,
    actor_role: Role,
) -> None:
    """Delete a catalog record that nothing references.

    Args:
        session: Open database session. The caller commits.
        record: Record to delete.
        record_id: Its primary key.
        references: Columns that may point at it.
        actor_role: Role of the user asking for the deletion.

    Raises:
        PermissionDeniedError: If the role is not an administrator.
        InUseError: If any record still points at it.
    """
    require_permission(actor_role, Permission.ADMINISTER_SYSTEM)
    usage = count_references(session, record_id, references)
    if usage:
        detail = ", ".join(f"{count} {label}" for label, count in usage.items())
        raise InUseError(f"{type(record).__name__} {record_id} is referenced by {detail}.")
    session.delete(record)
    session.flush()
