from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class TokenBucket:
    """Simple thread-safe token bucket. Use one per upstream rate-limited host."""

    rate_per_sec: float
    capacity: int

    def __post_init__(self) -> None:
        if self.rate_per_sec <= 0 or self.capacity <= 0:
            raise ValueError("rate_per_sec and capacity must be positive")
        self._tokens = float(self.capacity)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, n: int = 1) -> None:
        if n <= 0:
            raise ValueError("acquire(n) requires n >= 1")
        while True:
            with self._lock:
                now = time.monotonic()
                self._tokens = min(
                    self.capacity,
                    self._tokens + (now - self._last_refill) * self.rate_per_sec,
                )
                self._last_refill = now
                if self._tokens >= n:
                    self._tokens -= n
                    return
                wait = (n - self._tokens) / self.rate_per_sec
            time.sleep(wait)
