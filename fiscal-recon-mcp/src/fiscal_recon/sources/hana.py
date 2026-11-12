"""
sources/hana.py

Adapter for the ERP system, modeled on SAP HANA (hdbcli). hdbcli has no
built-in pool, so this uses SimpleConnectionPool instead of the single
shared connection the previous version kept open.
"""

from __future__ import annotations

import datetime
from typing import Any, Callable

from fiscal_recon.models import FiscalRecord
from fiscal_recon.sources.base import rows_to_records
from fiscal_recon.sources.pool import SimpleConnectionPool

_SQL = """
    SELECT ORIGIN_BRANCH, DESTINATION_BRANCH, DOCUMENT_NUMBER, SERIES,
           ISSUE_DATE, NET_VALUE, TAX_VALUE
    FROM ERP_FISCAL_DOCUMENTS
    WHERE ISSUE_DATE = ?
"""


class HanaSource:
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        name: str = "erp",
        pool_max: int = 4,
        connect: Callable[[], Any] | None = None,
    ):
        """`connect` can be injected (tests); otherwise hdbcli is used."""
        if connect is None:
            from hdbcli import dbapi  # optional dependency: pip install .[hana]

            def connect():
                return dbapi.connect(address=host, port=port, user=user, password=password)

        self.name = name
        self._pool = SimpleConnectionPool(connect, max_size=pool_max)

    def fetch_records(self, reference_date: datetime.date) -> list[FiscalRecord]:
        with self._pool.connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(_SQL, (reference_date,))
                rows = cursor.fetchall()
            finally:
                cursor.close()
        return rows_to_records(rows)
