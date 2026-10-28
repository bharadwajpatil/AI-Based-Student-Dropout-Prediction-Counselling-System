from datetime import UTC, datetime, timedelta

from backend.app.core.clock import SystemClock, TestClock


def test_system_clock_returns_timezone_aware_utc():
    clock = SystemClock()
    now = clock.now()
    assert now.tzinfo is not None
    assert now.tzinfo == UTC


def test_test_clock_advance_deterministic():
    start_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    clock = TestClock(initial_time=start_time)
    assert clock.now() == start_time

    # Advance by 15 minutes without sleeping
    clock.advance(timedelta(minutes=15))
    expected = datetime(2026, 1, 1, 12, 15, 0, tzinfo=UTC)
    assert clock.now() == expected


def test_test_clock_set_time():
    clock = TestClock()
    target_time = datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC)
    clock.set_time(target_time)
    assert clock.now() == target_time
