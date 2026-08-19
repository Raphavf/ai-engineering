"""
src/models.py

Pydantic v2 domain models describing the shapes of data flowing through
the system, validated at the boundary.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, computed_field


class BranchBalance(BaseModel):
    """A branch's balance as reported by one system, for one reference date."""

    branch_code: str
    reference_date: str  # ISO format
    net_value: float
    tax_value: float


class BranchDivergence(BaseModel):
    """Comparison result for one branch: legacy value vs ERP value."""

    branch_code: str
    reference_date: str
    legacy_net_value: float
    erp_net_value: float

    @computed_field  # type: ignore[misc]
    @property
    def divergence_percentage(self) -> float:
        """Derived from the two values above, so it never gets out of sync with them."""
        if self.legacy_net_value == 0:
            return 0.0 if self.erp_net_value == 0 else 100.0
        difference = abs(self.legacy_net_value - self.erp_net_value)
        return round((difference / abs(self.legacy_net_value)) * 100, 2)


class ReconciliationRequest(BaseModel):
    """Request payload for triggering a reconciliation run over the API."""

    reference_date: str = Field(..., description="ISO format date, YYYY-MM-DD.")
