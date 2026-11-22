"""Time helpers.

Every timestamp in the MES is recorded in UTC so that records from different computers can be
compared; screens convert to local time when displaying.
"""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime.

    Returns:
        The current instant in UTC.
    """
    return datetime.now(UTC)
