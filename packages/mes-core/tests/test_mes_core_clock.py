from datetime import UTC, datetime, timedelta

from mes_core.clock import utc_now


def test_utc_now_is_timezone_aware_utc():
    now = utc_now()
    assert now.tzinfo is UTC


def test_utc_now_is_current():
    assert abs(utc_now() - datetime.now(UTC)) < timedelta(seconds=5)
