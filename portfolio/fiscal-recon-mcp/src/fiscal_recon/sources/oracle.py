"""
sources/oracle.py

Adapter for the legacy (source-of-truth) system, modeled on Oracle.
Uses oracledb's built-in connection pool.
"""

from __future__ import annotations

import datetime

from fiscal_recon.models import FiscalRecord
from fiscal_recon.sources.base import rows_to_records

_SQL = """
    SELECT origin_branch, destination_branch, document_number, series,
           issue_date, net_value, tax_value
    FROM legacy_fiscal_documents
    WHERE issue_date = :reference_date
"""


class OracleSource:
    def __init__(self, user: str, password: str, dsn: str, name: str = "legacy", pool_max: int = 4):
        import oracledb  # optional dependency: pip install .[oracle]

        self.name = name
        self._pool = oracledb.create_pool(
            user=user, password=password, dsn=dsn, min=1, max=pool_max, increment=1
        )

    def fetch_records(self, reference_date: datetime.date) -> list[FiscalRecord]:
        with self._pool.acquire() as conn:
            with conn.cursor() as cursor:
                cursor.execute(_SQL, reference_date=reference_date)
                rows = cursor.fetchall()
        # oracledb returns DATE columns as datetime; keep only the date part
        return rows_to_records(
            [(*r[:4], r[4].date() if isinstance(r[4], datetime.datetime) else r[4], *r[5:]) for r in rows]
        )
