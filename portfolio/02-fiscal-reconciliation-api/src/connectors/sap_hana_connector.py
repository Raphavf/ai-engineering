"""
src/connectors/sap_hana_connector.py

Connector for the ERP system, modeled on SAP HANA (via hdbcli). Mirrors
oracle_connector.py's structure for consistency.
"""

from __future__ import annotations

from src.config import settings
from src.models import BranchBalance

_connection = None


def _ensure_connection():
    """Create the connection on first use."""
    global _connection
    if _connection is None:
        from hdbcli import dbapi  # optional dependency

        _connection = dbapi.connect(
            address=settings.erp_system_host,
            port=settings.erp_system_port,
        )
    return _connection


def fetch_erp_balances(reference_date: str) -> list[BranchBalance]:
    """Fetch one balance row per branch from the ERP system for a given date."""
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
