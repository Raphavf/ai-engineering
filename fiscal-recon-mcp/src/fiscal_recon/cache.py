"""
cache.py

Small in-memory TTL cache. Avoids re-querying both databases when an
agent calls several tools in a row for the same date. The clock is
injectable so expiry can be tested without sleeping.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Generic, Hashable, TypeVar

V = TypeVar("V")


class TTLCache(Generic[V]):
    def __init__(self, ttl_seconds: float, max_entries: int = 64, clock: Callable[[], float] = time.monotonic):
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._clock = clock
        self._data: dict[Hashable, tuple[float, V]] = {}
        self._lock = threading.Lock()

    def get_or_compute(self, key: Hashable, compute: Callable[[], V]) -> V:
        now = self._clock()
        with self._lock:
            entry = self._data.get(key)
            if entry and now - entry[0] < self._ttl:
                return entry[1]

        value = compute()  # outside the lock: DB queries can be slow

        with self._lock:
            if len(self._data) >= self._max_entries and key not in self._data:
                oldest = min(self._data, key=lambda k: self._data[k][0])
                del self._data[oldest]
            self._data[key] = (now, value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
