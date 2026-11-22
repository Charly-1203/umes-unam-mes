"""Custom column types."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, Dialect, Enum
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """Datetime column that always stores and returns timezone-aware UTC values.

    SQLite has no timezone support and returns naive datetimes; this type normalizes values on
    the way in and marks them as UTC on the way out, so the rest of the code never has to deal
    with naive datetimes. A naive value written by the application is assumed to be UTC.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        """Convert a value to UTC before storing it.

        Args:
            value: Datetime to store.
            dialect: Database dialect in use.

        Returns:
            The value converted to UTC.
        """
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        """Mark a stored value as UTC when reading it.

        Args:
            value: Datetime read from the database.
            dialect: Database dialect in use.

        Returns:
            A timezone-aware UTC datetime.
        """
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def enum_type(enum_cls: type[StrEnum]) -> Enum:
    """Build a column type that stores an enumeration by its value.

    Values (``"operator"``) are stored instead of member names (``"OPERATOR"``) so the database
    shows the same text as the JSON messages. A plain string column is used on every database,
    which keeps migrations simple when new members are added.

    Args:
        enum_cls: Enumeration to store.

    Returns:
        The SQLAlchemy column type.
    """
    return Enum(
        enum_cls,
        values_callable=lambda members: [member.value for member in members],
        native_enum=False,
        length=32,
        validate_strings=True,
    )
