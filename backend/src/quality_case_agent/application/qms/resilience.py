"""Small deterministic rate-limit and circuit-breaker modules for QMS calls."""

import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from quality_case_agent.application.ports.qms import QmsTransientError


class TokenBucketRateLimiter:
    def __init__(self, rate_per_second: float = 10.0, burst: int = 10, clock: Callable[[], float] | None = None) -> None:
        if rate_per_second <= 0 or burst < 1:
            raise ValueError("rate_per_second must be positive and burst must be >= 1")
        self._rate = rate_per_second
        self._burst = float(burst)
        self._tokens = float(burst)
        self._last = (clock or time.monotonic)()
        self._clock = clock or time.monotonic

    def acquire(self) -> bool:
        now = self._clock()
        self._tokens = min(self._burst, self._tokens + max(0.0, now - self._last) * self._rate)
        self._last = now
        if self._tokens < 1.0:
            return False
        self._tokens -= 1.0
        return True


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, open_for: timedelta = timedelta(seconds=30), clock: Callable[[], datetime] | None = None) -> None:
        if failure_threshold < 1 or open_for <= timedelta(0):
            raise ValueError("invalid circuit-breaker settings")
        self._threshold = failure_threshold
        self._open_for = open_for
        self._clock = clock or (lambda: datetime.now(UTC))
        self._failures = 0
        self._opened_at: datetime | None = None

    def before_call(self) -> None:
        if self._opened_at is not None:
            if self._clock() - self._opened_at < self._open_for:
                raise QmsTransientError("QMS circuit breaker is open")
            self._opened_at = None
            self._failures = 0

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._threshold:
            self._opened_at = self._clock()
