"""Workstations of the line."""

from sqlmodel import Session, select

from mes_core.enums import Role
from mes_server.db.models import DowntimeEvent, ExecutionRecord, RecipeStep, Station
from mes_server.services import catalog
from mes_server.services.validation import normalize_code, optional_text, required_text

REFERENCES = (
    catalog.Reference("recipe steps", RecipeStep.station_id),
    catalog.Reference("execution records", ExecutionRecord.station_id),
    catalog.Reference("downtime events", DowntimeEvent.station_id),
)
"""Records that point at a station and therefore keep it from being deleted."""


def list_stations(session: Session, *, include_inactive: bool = False) -> list[Station]:
    """Return stations ordered by code.

    Args:
        session: Open database session.
        include_inactive: Also return deactivated stations.

    Returns:
        The stations.
    """
    statement = select(Station).order_by(Station.code)
    if not include_inactive:
        statement = statement.where(Station.is_active == True)  # noqa: E712
    return list(session.exec(statement).all())


def get_station(session: Session, station_id: int) -> Station:
    """Load a station.

    Args:
        session: Open database session.
        station_id: Primary key.

    Returns:
        The station.

    Raises:
        NotFoundError: If it does not exist.
    """
    return catalog.get_or_raise(session, Station, station_id)


def create_station(
    session: Session, *, code: str, name: str, description: str | None = None
) -> Station:
    """Create a station.

    Args:
        session: Open database session. The caller commits.
        code: Unique code, normalized to uppercase; it also addresses the station's gateway.
        name: Human-readable name.
        description: Optional free text.

    Returns:
        The new station.

    Raises:
        ValidationError: If a field breaks the rules.
        AlreadyExistsError: If the code is taken.
    """
    normalized = normalize_code(code, max_length=32)
    station = Station(
        code=normalized,
        name=required_text(name, field="name", max_length=128),
        description=optional_text(description, field="description", max_length=512),
    )
    catalog.ensure_code_available(session, Station, normalized)
    session.add(station)
    session.flush()
    return station


def update_station(
    session: Session, station_id: int, *, name: str, description: str | None = None
) -> Station:
    """Change a station's name and description. The code never changes.

    Args:
        session: Open database session. The caller commits.
        station_id: Primary key.
        name: New name.
        description: New description.

    Returns:
        The updated station.
    """
    station = get_station(session, station_id)
    station.name = required_text(name, field="name", max_length=128)
    station.description = optional_text(description, field="description", max_length=512)
    session.add(station)
    return station


def set_station_active(session: Session, station_id: int, active: bool) -> Station:
    """Activate or deactivate a station.

    Args:
        session: Open database session. The caller commits.
        station_id: Primary key.
        active: New state.

    Returns:
        The station.
    """
    station = get_station(session, station_id)
    catalog.set_active(station, active)
    session.add(station)
    return station


def station_usage(session: Session, station_id: int) -> dict[str, int]:
    """Count the records that reference a station.

    Args:
        session: Open database session.
        station_id: Primary key.

    Returns:
        Non-zero counts keyed by reference label.
    """
    return catalog.count_references(session, station_id, REFERENCES)


def delete_station(session: Session, station_id: int, *, actor_role: Role) -> None:
    """Delete a station without history.

    Args:
        session: Open database session. The caller commits.
        station_id: Primary key.
        actor_role: Role of the user asking for the deletion.

    Raises:
        NotFoundError: If it does not exist.
        PermissionDeniedError: If the role is not an administrator.
        InUseError: If recipe steps, executions or downtime reference it.
    """
    station = get_station(session, station_id)
    catalog.delete_unused(session, station, station_id, REFERENCES, actor_role=actor_role)
