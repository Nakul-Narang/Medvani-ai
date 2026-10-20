"""API-key check and a small in-memory rate limiter."""

from __future__ import annotations

import hmac
import threading
import time
from collections import defaultdict, deque


def api_key_is_valid(provided: str | None, allowed: tuple[str, ...]) -> bool:
    """Constant-time comparison. An empty allow-list means auth is disabled."""
    if not allowed:
        return True
    if not provided:
        return False
    return any(hmac.compare_digest(provided.encode(), key.encode()) for key in allowed)


class SlidingWindowRateLimiter:
    """Per-key sliding window. Single-process only.

    For more than one instance, put a shared limiter in front (gateway, CDN,
    or Redis). This one still protects each instance from a single noisy client.
    """

    def __init__(self, limit_per_minute: int, window_seconds: float = 60.0) -> None:
        self._limit = limit_per_minute
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        if self._limit <= 0:
            return True, 0
        now = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self._window:
                hits.popleft()
            if len(hits) >= self._limit:
                return False, max(1, int(self._window - (now - hits[0])) + 1)
            hits.append(now)
            # Opportunistic cleanup so the dict cannot grow without bound.
            if len(self._hits) > 10_000:
                for stale in [k for k, v in self._hits.items() if not v or now - v[-1] >= self._window]:
                    self._hits.pop(stale, None)
            return True, 0
