"""
src/connectors/oracle_connector.py

Connector for the legacy (source-of-truth) system, modeled on Oracle.
This module exists as a clear seam between "business logic" and "how we
actually talk to a database" -- which is exactly the seam that makes
`tests/test_service.py` possible: tests mock this module's functions
instead of needing a real Oracle instance running in CI.
"""

from __future__ import annotations

from src.config import settings
from src.models import BranchBalance

_pool = None  # lazily created -- see _ensure_pool()


def _ensure_pool():
    """Create the connection pool on first real use.

    Importing this module (e.g. to patch it in a test) never opens a
    network connection -- only calling a function that actually needs
    data does.
    """
    global _pool
    if _pool is None:
        import oracledb  # imported lazily so this module can be imported
        # in environments/tests that don't have oracledb installed at all.

        _pool = oracledb.create_pool(
            dsn=settings.legacy_system_dsn,
            min=1,
            max=4,
            increment=1,
        )
    return _pool


def fetch_legacy_balances(reference_date: str) -> list[BranchBalance]:
    """Fetch one balance row per branch from the legacy system for a
    given reference date.

    In tests, this function is replaced entirely via
    `unittest.mock.patch`, so the SQL below never actually runs outside
    a real deployment.
    """
    pool = _ensure_pool()
    connection = pool.acquire()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT branch_code, net_value, tax_value
            FROM legacy_branch_balances
            WHERE reference_date = :reference_date
            """,
            reference_date=reference_date,
        )
        return [
            BranchBalance(
                branch_code=row[0],
                reference_date=reference_date,
                net_value=row[1],
                tax_value=row[2],
            )
            for row in cursor.fetchall()
        ]
    finally:
        pool.release(connection)
