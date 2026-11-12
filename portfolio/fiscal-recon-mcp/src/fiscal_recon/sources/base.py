"""
sources/base.py

The adapter contract every ERP connector implements. The reconciliation
service only depends on this Protocol, so adding a new ERP means writing
one new adapter -- nothing in reconciliation.py, the MCP server or the API
changes.
"""

from __future__ import annotations

import datetime
from typing import Protocol, runtime_checkable

from fiscal_recon.models import FiscalRecord


@runtime_checkable
class RecordSource(Protocol):
    """Anything that can return the fiscal documents issued on a given date."""

    name: str

    def fetch_records(self, reference_date: datetime.date) -> list[FiscalRecord]: ...


def rows_to_records(rows) -> list[FiscalRecord]:
    """Convert DB-API rows in canonical column order into validated records.

    Every adapter's SQL must select, in this order:
    origin_branch, destination_branch, document_number, series,
    issue_date, net_value, tax_value
    """
    return [
        FiscalRecord(
            origin_branch=str(r[0]),
            destination_branch=str(r[1]),
            document_number=str(r[2]),
            series=str(r[3]),
            issue_date=r[4],
            net_value=float(r[5]),
            tax_value=float(r[6]),
        )
        for r in rows
    ]
