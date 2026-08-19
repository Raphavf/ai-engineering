"""
connectors.py

Pooled database connections for the two systems being reconciled:
- LEGACY system (modeled on Oracle, via oracledb)
- ERP system (modeled on SAP HANA, via hdbcli)

Pooling avoids opening a new connection on every query -- important once
an agent can call the same tool multiple times in one conversation.
Credentials are loaded through security.secrets_manager instead of being
hardcoded here.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from security.secrets_manager import get_credentials

try:
    import oracledb
except ImportError:  # not installed in every environment
    oracledb = None

try:
    from hdbcli import dbapi as hana_dbapi
except ImportError:
    hana_dbapi = None


_legacy_pool = None
_erp_pool = None


def _ensure_legacy_pool():
    """Create the legacy-system pool on first use."""
    global _legacy_pool
    if _legacy_pool is None:
        if oracledb is None:
            raise RuntimeError("oracledb is not installed.")
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
    """Create the ERP-system connection on first use."""
    global _erp_pool
    if _erp_pool is None:
        if hana_dbapi is None:
            raise RuntimeError("hdbcli is not installed.")
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
    """Borrow a connection from the legacy-system pool, returned when done."""
    pool = _ensure_legacy_pool()
    connection = pool.acquire()
    try:
        yield connection
    finally:
        pool.release(connection)


@contextmanager
def get_erp_connection():
    """Borrow the ERP-system connection."""
    connection = _ensure_erp_pool()
    yield connection
