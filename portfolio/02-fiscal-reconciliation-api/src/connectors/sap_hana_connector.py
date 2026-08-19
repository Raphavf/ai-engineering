"""
src/connectors/sap_hana_connector.py

Connector for the ERP system, modeled on SAP HANA (via hdbcli). Mirrors
the shape of oracle_connector.py deliberately -- same lazy-init pattern,
same "one function per real use case" style -- so a reader who understood
one connector already understands this one.
"""

from __future__ import annotations

from src.config import settings
from src.models import BranchBalance

_connection = None


def _ensure_connection():
    global _connection
    if _connection is None:
        from hdbcli import dbapi  # optional dependency, imported lazily

        _connection = dbapi.connect(
            address=settings.erp_system_host,
            port=settings.erp_system_port,
        )
    return _connection


def fetch_erp_balances(reference_date: str) -> list[BranchBalance]:
    """Fetch one balance row per branch from the ERP system for a given
    reference date. Replaced by a mock in unit tests -- see
    tests/test_service.py.
    """
    connection = _ensure_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT BRANCH_CODE, NET_VALUE, TAX_VALUE
        FROM ERP_BRANCH_BALANCES
        WHERE REFERENCE_DATE = ?
        """,
        (reference_date,),
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
