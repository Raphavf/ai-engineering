"""
connectors.py

Pooled database connections for the two systems this project reconciles:

    - the LEGACY system  (modeled here on Oracle, via `oracledb`)
    - the ERP system      (modeled here on SAP HANA, via `hdbcli`)

Why pooling matters
--------------------
A naive approach opens a new connection every time a query needs to run.
That's fine for a one-off script. It stops being fine the moment an LLM
agent can call your tool multiple times in a single conversation — you'd
be paying the (slow) connection-handshake cost on every single call.
`connection pooling` keeps a small set of already-open connections ready
to reuse, so repeated tool calls stay fast.

Credentials are never hardcoded here — they're loaded through
`security.secrets_manager`, which decrypts them at runtime instead of
storing them in plaintext config files or source control.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from security.secrets_manager import get_credentials

# These imports are optional/lazy in the real project because not every
# environment running this code has both database drivers installed.
try:
    import oracledb
except ImportError:  # pragma: no cover - environment-dependent
    oracledb = None

try:
    from hdbcli import dbapi as hana_dbapi
except ImportError:  # pragma: no cover - environment-dependent
    hana_dbapi = None


# Module-level pool objects. Created lazily on first use (see
# `_ensure_legacy_pool`) rather than at import time, so importing this
# module never has side effects like opening a network connection.
_legacy_pool = None
_erp_pool = None


def _ensure_legacy_pool():
    """Create the legacy-system connection pool on first use.

    Lazy initialization matters here: this module can be imported (for
    type-checking, testing with mocks, etc.) without ever touching the
    network, as long as nothing actually calls a query function.
    """
    global _legacy_pool
    if _legacy_pool is None:
        if oracledb is None:
            raise RuntimeError(
                "oracledb is not installed. Install it or mock this pool "
                "in tests instead of calling it for real."
            )
        credentials = get_credentials("legacy_system")
        _legacy_pool = oracledb.create_pool(
            user=credentials.username,
            password=credentials.password,
            dsn=credentials.dsn,
            min=1,
            max=4,
            increment=1,
        )
    return _legacy_pool


def _ensure_erp_pool():
    """Create the ERP-system (SAP HANA-style) connection pool on first use.

    hdbcli doesn't ship a built-in pool the way oracledb does, so this
    keeps a single long-lived connection and relies on the caller not to
    hold it open across unrelated requests. A production system with
    heavier concurrency would wrap this in its own lightweight pool.
    """
    global _erp_pool
    if _erp_pool is None:
        if hana_dbapi is None:
            raise RuntimeError(
                "hdbcli is not installed. Install it or mock this "
                "connection in tests instead of calling it for real."
            )
        credentials = get_credentials("erp_system")
        _erp_pool = hana_dbapi.connect(
            address=credentials.host,
            port=credentials.port,
            user=credentials.username,
            password=credentials.password,
        )
    return _erp_pool


@contextmanager
def get_legacy_connection() -> Iterator["oracledb.Connection"]:
    """Borrow a connection from the legacy-system pool.

    Using a context manager here (instead of returning the connection
    directly) guarantees the connection is returned to the pool even if
    the caller's query raises an exception — no leaked connections.
    """
    pool = _ensure_legacy_pool()
    connection = pool.acquire()
    try:
        yield connection
    finally:
        pool.release(connection)


@contextmanager
def get_erp_connection():
    """Borrow the ERP-system connection.

    Kept as a context manager for symmetry with `get_legacy_connection`,
    even though the underlying object here isn't pool-backed in this
    simplified version.
    """
    connection = _ensure_erp_pool()
    yield connection
