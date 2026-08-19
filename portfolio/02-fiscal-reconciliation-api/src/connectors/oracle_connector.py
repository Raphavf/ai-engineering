"""
src/connectors/oracle_connector.py

Connector for the legacy (source-of-truth) system, modeled on Oracle.
Kept separate from service.py so tests can mock this module instead of
needing a real database.
"""

from __future__ import annotations

from src.config import settings
from src.models import BranchBalance

_pool = None


def _ensure_pool():
    """Create the connection pool on first use."""
    global _pool
    if _pool is None:
        import oracledb  # imported lazily, optional dependency

        _pool = oracledb.create_pool(
            dsn=settings.legacy_system_dsn,
            min=1,
            max=4,
            increment=1,
        )
    return _pool


def fetch_legacy_balances(reference_date: str) -> list[BranchBalance]:
    """Fetch one balance row per branch from the legacy system for a given date."""
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
