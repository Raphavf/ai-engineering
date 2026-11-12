"""
models.py

Domain models shared by every layer (sources, reconciliation, MCP, API).
Validated with Pydantic v2 at the boundary where data enters the system.
"""

from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field

# Composite key used to match one fiscal document across systems
KEY_FIELDS = ["origin_branch", "destination_branch", "document_number", "series"]

# Numeric columns being compared
VALUE_FIELDS = ["net_value", "tax_value"]

RecordStatus = Literal["ok", "missing_in_erp", "value_divergent"]


class FiscalRecord(BaseModel):
    """One fiscal document as reported by one system."""

    origin_branch: str
    destination_branch: str
    document_number: str
    series: str
    issue_date: datetime.date
    net_value: float
    tax_value: float


class ReconciliationSummary(BaseModel):
    """Aggregated result of one reconciliation run."""

    reference_date: datetime.date
    total_records: int
    missing_in_erp: int
    value_divergent: int
    matching: int


class BranchDivergence(BaseModel):
    """Branch-level roll-up: total legacy value vs total ERP value."""

    branch_code: str
    reference_date: datetime.date
    divergent_documents: int
    legacy_net_value: float
    erp_net_value: float

    @computed_field  # type: ignore[prop-decorator]
    @property
    def divergence_percentage(self) -> float:
        """Derived from the two totals, so it can never drift out of sync with them."""
        if self.legacy_net_value == 0:
            return 0.0 if self.erp_net_value == 0 else 100.0
        difference = abs(self.legacy_net_value - self.erp_net_value)
        return round(difference / abs(self.legacy_net_value) * 100, 2)


class ReconciliationRequest(BaseModel):
    """Request payload for the REST API."""

    reference_date: str = Field(..., description="ISO format date, YYYY-MM-DD.")
