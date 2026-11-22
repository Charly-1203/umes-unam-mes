from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy.dialects import sqlite

from mes_server.db.types import UTCDateTime

DIALECT = sqlite.dialect()
MEXICO_CITY = timezone(timedelta(hours=-6))


@pytest.fixture
def column_type():
    return UTCDateTime()


def test_naive_value_is_assumed_to_be_utc(column_type):
    stored = column_type.process_bind_param(datetime(2026, 11, 20, 12, 0), DIALECT)
    assert stored == datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


def test_other_timezones_are_converted_to_utc(column_type):
    local = datetime(2026, 11, 20, 6, 0, tzinfo=MEXICO_CITY)
    stored = column_type.process_bind_param(local, DIALECT)
    assert stored == datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
    assert stored.tzinfo is UTC


def test_values_read_back_are_utc(column_type):
    loaded = column_type.process_result_value(datetime(2026, 11, 20, 12, 0), DIALECT)
    assert loaded.tzinfo is UTC


def test_aware_values_read_back_are_converted_to_utc(column_type):
    loaded = column_type.process_result_value(
        datetime(2026, 11, 20, 6, 0, tzinfo=MEXICO_CITY), DIALECT
    )
    assert loaded == datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize("method", ["process_bind_param", "process_result_value"])
def test_none_is_preserved(column_type, method):
    assert getattr(column_type, method)(None, DIALECT) is None
