"""Small shared, per-provider request throttle for public APIs."""

from __future__ import annotations

import time
from collections import deque
from threading import Lock


class RateLimiter:
    def __init__(self, requests: int, period_seconds: float = 60.0, *, clock=time.monotonic,
                 sleeper=time.sleep):
        if requests < 1 or period_seconds <= 0:
            raise ValueError("requests and period_seconds must be positive")
        self.requests = requests
        self.period_seconds = period_seconds
        self._clock = clock
        self._sleep = sleeper
        self._calls: deque[float] = deque()
        self._lock = Lock()

    def wait(self) -> None:
        with self._lock:
            now = self._clock()
            while self._calls and now - self._calls[0] >= self.period_seconds:
                self._calls.popleft()
            if len(self._calls) >= self.requests:
                self._sleep(self.period_seconds - (now - self._calls[0]))
                now = self._clock()
                while self._calls and now - self._calls[0] >= self.period_seconds:
                    self._calls.popleft()
            self._calls.append(self._clock())


class ProviderThrottles:
    """Separate budgets for endpoint classes whose provider limits differ."""

    def __init__(self):
        self.dexscreener_profiles = RateLimiter(60)
        self.dexscreener_pairs = RateLimiter(300)
        self.geckoterminal = RateLimiter(30)
        self.defillama = RateLimiter(30)
