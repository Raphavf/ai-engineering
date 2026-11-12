"""
sources/sqlite.py

SQLite adapter, used for local development, demos and the test suite
with synthetic data (see synthetic.py). Both "systems" can live in one
SQLite file as two tables, or in two files.
"""

from __future__ import annotations

import datetime
import re
import sqlite3
from pathlib import Path

from fiscal_recon.models import FiscalRecord
from fiscal_recon.sources.base import rows_to_records
from fiscal_recon.sources.pool import SimpleConnectionPool

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class SqliteSource:
    def __init__(self, name: str, db_path: str | Path, table: str, max_connections: int = 4):
        if not _IDENTIFIER.match(table):
            raise ValueError(f"Invalid table name: {table!r}")
        self.name = name
        self._table = table
        self._pool = SimpleConnectionPool(
            lambda: sqlite3.connect(str(db_path), check_same_thread=False),
            max_size=max_connections,
        )

    def fetch_records(self, reference_date: datetime.date) -> list[FiscalRecord]:
        sql = (
            "SELECT origin_branch, destination_branch, document_number, series, "
            "issue_date, net_value, tax_value "
            f"FROM {self._table} WHERE issue_date = ?"
        )
        with self._pool.connection() as conn:
            rows = conn.execute(sql, (reference_date.isoformat(),)).fetchall()
        return rows_to_records(rows)
