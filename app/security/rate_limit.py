from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic


class InMemoryRateLimiter:
    """Límite por clave y ventana con memoria acotada para una sola instancia."""

    def __init__(
        self,
        max_requests: int,
        window_seconds: int,
        *,
        max_keys: int = 10_000,
    ) -> None:
        if max_requests < 1:
            raise ValueError("max_requests debe ser >= 1.")
        if window_seconds < 1:
            raise ValueError("window_seconds debe ser >= 1.")
        if max_keys < 1:
            raise ValueError("max_keys debe ser >= 1.")
        self._max_requests = max_requests
        self._window_seconds = float(window_seconds)
        self._max_keys = max_keys
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _purge_stale_keys(self, cutoff: float) -> None:
        stale = [
            key
            for key, bucket in self._hits.items()
            if not bucket or bucket[-1] <= cutoff
        ]
        for key in stale:
            self._hits.pop(key, None)

    def allow(self, key: str, *, now: float | None = None) -> bool:
        timestamp = monotonic() if now is None else now
        cutoff = timestamp - self._window_seconds
        with self._lock:
            if key not in self._hits and len(self._hits) >= self._max_keys:
                self._purge_stale_keys(cutoff)
                if len(self._hits) >= self._max_keys:
                    return False

            bucket = self._hits[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self._max_requests:
                return False
            bucket.append(timestamp)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
