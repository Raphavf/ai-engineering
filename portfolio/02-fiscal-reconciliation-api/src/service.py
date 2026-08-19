"""
src/service.py

The reconciliation algorithm, expressed in terms of the typed models from
models.py instead of raw dicts/DataFrames. This is deliberately simpler
than the pandas-based version in project 01 -- it's built to show the same
core idea (compare two data sources, flag divergences) in a way that's
easy to unit test with plain Python objects and mocked connectors.
"""

from __future__ import annotations

from src.connectors.oracle_connector import fetch_legacy_balances
from src.connectors.sap_hana_connector import fetch_erp_balances
from src.models import BranchBalance, BranchDivergence

# Same zero-tolerance rule as project 01: any non-zero difference counts.
DIVERGENCE_TOLERANCE = 0.0


def reconcile_branches(reference_date: str) -> list[BranchDivergence]:
    """Fetch balances from both systems for `reference_date` and return
    the divergences between them.

    Only branches present in the legacy system are considered -- the
    legacy system is the source of truth, so a branch that legacy doesn't
    know about isn't this reconciliation's concern.
    """
    legacy_balances = fetch_legacy_balances(reference_date)
    erp_balances = {b.branch_code: b for b in fetch_erp_balances(reference_date)}

    divergences: list[BranchDivergence] = []
    for legacy in legacy_balances:
        erp_match = erp_balances.get(legacy.branch_code)
        erp_net_value = erp_match.net_value if erp_match else 0.0

        if round(abs(legacy.net_value - erp_net_value), 2) > DIVERGENCE_TOLERANCE:
            divergences.append(
                BranchDivergence(
                    branch_code=legacy.branch_code,
                    reference_date=reference_date,
                    legacy_net_value=legacy.net_value,
                    erp_net_value=erp_net_value,
                )
            )

    return divergences
