from collections import defaultdict
from datetime import datetime, timedelta

from backend.app.core.clock import Clock, get_clock


class InMemoryRateLimiter:
    """Thread-safe and async-safe in-memory rate limiter using injected Clock."""

    def __init__(self, clock: Clock | None = None) -> None:
        self.clock = clock or get_clock()
        # Storage: key -> list of UTC timestamps
        self._history: dict[str, list[datetime]] = defaultdict(list)

    def _prune(self, key: str, window: timedelta) -> None:
        now = self.clock.now()
        cutoff = now - window
        self._history[key] = [ts for ts in self._history[key] if ts > cutoff]

    def is_allowed(self, key: str, limit: int, window: timedelta) -> bool:
        """Checks whether an action under `key` is allowed and records the attempt."""
        self._prune(key, window)
        if len(self._history[key]) >= limit:
            return False
        self._history[key].append(self.clock.now())
        return True

    def check_only(self, key: str, limit: int, window: timedelta) -> bool:
        """Checks limit without recording an attempt."""
        self._prune(key, window)
        return len(self._history[key]) < limit

    def seconds_until_allowed(self, key: str, min_interval: timedelta) -> int:
        """Returns remaining cooldown seconds if minimum interval between actions is violated."""
        if not self._history[key]:
            return 0
        last_time = max(self._history[key])
        now = self.clock.now()
        elapsed = now - last_time
        if elapsed < min_interval:
            return int((min_interval - elapsed).total_seconds())
        return 0

    def reset(self, key: str | None = None) -> None:
        """Clears rate limit history."""
        if key:
            self._history.pop(key, None)
        else:
            self._history.clear()


# Global rate limiter instance
rate_limiter = InMemoryRateLimiter()
