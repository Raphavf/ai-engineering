"""
src/models.py

Pydantic v2 domain models. These describe the SHAPE of the data flowing
through the system and validate it at the boundary, so nothing downstream
has to re-check "is this actually a number?" ever again.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, computed_field


class BranchBalance(BaseModel):
    """A single branch's balance as reported by one system, for one
    reference date. This is the raw building block both the legacy-system
    and ERP-system extraction functions return.
    """

    branch_code: str
    reference_date: str  # ISO format, kept as str at this layer on purpose:
    # date parsing/validation happens once, at the API boundary
    # (see api.py), not silently re-parsed everywhere this model is used.
    net_value: float
    tax_value: float


class BranchDivergence(BaseModel):
    """The comparison result for one branch: legacy value vs ERP value,
    plus a computed convenience field for how far apart they are.
    """

    branch_code: str
    reference_date: str
    legacy_net_value: float
    erp_net_value: float

    @computed_field  # type: ignore[misc]
    @property
    def divergence_percentage(self) -> float:
        """Computed, not stored: this is always derived from the two raw
        values above, so it can never drift out of sync with them the way
        a manually-maintained field could if someone updates one value
        and forgets the other.

        Guards against division by zero: if the legacy value is 0, we
        report 100% divergence whenever the ERP value differs from it at
        all, and 0% if both are exactly zero.
        """
        if self.legacy_net_value == 0:
            return 0.0 if self.erp_net_value == 0 else 100.0
        difference = abs(self.legacy_net_value - self.erp_net_value)
        return round((difference / abs(self.legacy_net_value)) * 100, 2)


class ReconciliationRequest(BaseModel):
    """Request payload for triggering a reconciliation run over the API."""

    reference_date: str = Field(
        ..., description="ISO format date, YYYY-MM-DD. Must fall within the allowed lookback window."
    )
