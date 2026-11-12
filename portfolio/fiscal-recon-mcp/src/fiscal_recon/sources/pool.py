"""
sources/pool.py

A small bounded connection pool for drivers that don't ship one
(hdbcli, sqlite3). oracledb has its own pool, so OracleSource uses that.

Connections are created lazily up to `max_size`; callers block (with a
timeout) once every connection is borrowed.
"""

from __future__ import annotations

import queue
import threading
from contextlib import contextmanager
from typing import Any, Callable, Iterator


class PoolExhaustedError(RuntimeError):
    """Raised when no connection is released within the timeout."""


class SimpleConnectionPool:
    def __init__(self, connect: Callable[[], Any], max_size: int = 4, timeout: float = 10.0):
        if max_size < 1:
            raise ValueError("max_size must be at least 1")
        self._connect = connect
        self._max_size = max_size
        self._timeout = timeout
        self._idle: queue.LifoQueue = queue.LifoQueue()
        self._created = 0
        self._lock = threading.Lock()

    @property
    def size(self) -> int:
        """How many connections have been opened so far."""
        return self._created

    def _acquire(self):
        try:
            return self._idle.get_nowait()
        except queue.Empty:
            pass

        with self._lock:
            if self._created < self._max_size:
                self._created += 1
                try:
                    return self._connect()
                except Exception:
                    self._created -= 1
                    raise

        try:
            return self._idle.get(timeout=self._timeout)
        except queue.Empty as exc:
            raise PoolExhaustedError(
                f"No connection released within {self._timeout}s (max_size={self._max_size})"
            ) from exc

    @contextmanager
    def connection(self) -> Iterator[Any]:
        """Borrow a connection; it goes back to the pool when the block exits.

        A connection that raised is closed and discarded instead of
        returned, so a broken connection isn't handed to the next caller.
        """
        conn = self._acquire()
        try:
            yield conn
        except Exception:
            self._discard(conn)
            raise
        else:
            self._idle.put(conn)

    def _discard(self, conn) -> None:
        try:
            conn.close()
        except Exception:
            pass
        with self._lock:
            self._created -= 1

    def close_all(self) -> None:
        while True:
            try:
                self._discard(self._idle.get_nowait())
            except queue.Empty:
                break
