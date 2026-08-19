"""
src/service.py

The reconciliation algorithm, built on the typed models from models.py
instead of raw dicts/DataFrames.
"""

from __future__ import annotations

from src.connectors.oracle_connector import fetch_legacy_balances
from src.connectors.sap_hana_connector import fetch_erp_balances
from src.models import BranchBalance, BranchDivergence

DIVERGENCE_TOLERANCE = 0.0


def reconcile_branches(reference_date: str) -> list[BranchDivergence]:
    """Fetch balances from both systems and return the divergences between them.

    Only branches present in the legacy system are considered, since it's
    the source of truth.
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
