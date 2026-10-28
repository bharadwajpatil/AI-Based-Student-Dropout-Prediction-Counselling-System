from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta


class Clock(ABC):
    """Abstract clock interface for injecting time across the system."""

    @abstractmethod
    def now(self) -> datetime:
        """Returns the current timezone-aware UTC datetime."""
        pass


class SystemClock(Clock):
    """Real system clock returning current UTC time."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class TestClock(Clock):
    """Controllable clock for unit and integration testing without sleeping."""

    __test__ = False

    def __init__(self, initial_time: datetime | None = None) -> None:
        self._current_time = initial_time or datetime.now(UTC)

    def now(self) -> datetime:
        return self._current_time

    def set_time(self, new_time: datetime) -> None:
        if new_time.tzinfo is None:
            new_time = new_time.replace(tzinfo=UTC)
        self._current_time = new_time

    def advance(self, duration: timedelta) -> None:
        self._current_time += duration


# Default system clock instance
default_clock: Clock = SystemClock()


def get_clock() -> Clock:
    """FastAPI dependency to retrieve the active clock."""
    return default_clock


from typing import overload


@overload
def ensure_utc(dt: None) -> None: ...


@overload
def ensure_utc(dt: datetime) -> datetime: ...


def ensure_utc(dt: datetime | None) -> datetime | None:
    """Ensures a datetime is timezone-aware in UTC (guards against naive DB datetimes)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)
