"""
reconciliation_service.py

Core business logic for comparing fiscal records between two systems:

    - LEGACY SYSTEM: treated as the source of truth (e.g. an older ERP or
      a dedicated tax-control database). We trust its numbers by default.
    - ERP SYSTEM: the newer/central system that should mirror the legacy
      data. Anything that doesn't match here is a "divergence" worth a
      human's attention.

This module has NO knowledge of MCP, LLMs, or agents. That's intentional:
business logic should be testable and usable on its own, with the AI-facing
layer (see server.py) as a thin wrapper on top. If you can't unit-test your
core logic without spinning up an LLM, the logic is in the wrong place.

The real-world version of this script compares fiscal notes (tax documents)
across a legacy Oracle database and SAP B1/HANA for a multi-branch retail
company. Names have been genericized here, but the comparison strategy is
the same one used in production.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

import pandas as pd

# ---------------------------------------------------------------------------
# Business rules, defined as module-level constants so they're easy to find
# and easy to explain to someone reviewing this code for the first time.
# ---------------------------------------------------------------------------

# The columns that uniquely identify one record across both systems.
# Think of this as a composite primary key used purely for matching rows
# between two different databases that don't share a common ID.
KEY_FIELDS = ["origin_branch", "destination_branch", "document_number", "series"]

# The numeric columns we actually compare for divergences.
VALUE_FIELDS = ["net_value", "tax_value"]

# Zero tolerance by default: ANY non-zero difference in a value field is
# reported. This mirrors the real business rule — fiscal numbers either
# match exactly or they get flagged, there is no "close enough".
DIVERGENCE_TOLERANCE = 0.0


@dataclass
class ReconciliationSummary:
    """Aggregated result of a reconciliation run.

    Using a dataclass (instead of a bare dict) means the shape of this
    result is documented in one place and IDEs/type-checkers can catch
    typos like `summary.mssing_in_erp` before they become a bug at 2am.
    """

    reference_date: str
    total_records: int
    missing_in_erp: int
    value_divergent: int
    matching: int


def extract_legacy_records(reference_date: datetime.date) -> pd.DataFrame:
    """Pull records from the legacy system starting at `reference_date`.

    In production this runs a bounded SQL query against the legacy
    database (see connectors.py). It's stubbed here with a clear
    NotImplementedError so this file stays runnable/importable as a
    portfolio piece without requiring real database access.
    """
    raise NotImplementedError(
        "Wire this up to connectors.get_legacy_connection() and run a "
        "date-bounded SELECT. See connectors.py for the pooled connection."
    )


def extract_erp_records(reference_date: datetime.date) -> pd.DataFrame:
    """Pull the equivalent records from the ERP system for comparison."""
    raise NotImplementedError(
        "Wire this up to connectors.get_erp_connection(). Same date bound "
        "as extract_legacy_records() so both sides cover the same window."
    )


def compare(legacy_df: pd.DataFrame, erp_df: pd.DataFrame) -> pd.DataFrame:
    """Compare legacy vs ERP records and flag divergences.

    Strategy: LEFT JOIN starting from the legacy system, because the
    legacy system is the source of truth. Anything present in the legacy
    system but absent from the ERP export shows up as NaN on the ERP
    side after the merge — that's exactly what we want to flag as
    "missing_in_erp".

    Args:
        legacy_df: records from the source-of-truth system.
        erp_df: records from the system being validated against it.

    Returns:
        A DataFrame with one row per legacy record, annotated with a
        `status` column: "missing_in_erp", "value_divergent", or "ok".
    """
    merged = legacy_df.merge(
        erp_df,
        on=KEY_FIELDS,
        how="left",
        suffixes=("_legacy", "_erp"),
    )

    def _classify_row(row: pd.Series) -> str:
        # If the ERP-side value column is NaN, the merge found no match
        # at all for this key — the record never made it into the ERP.
        if pd.isna(row.get(f"{VALUE_FIELDS[0]}_erp")):
            return "missing_in_erp"

        for field in VALUE_FIELDS:
            legacy_value = row[f"{field}_legacy"]
            erp_value = row[f"{field}_erp"]
            # Rounding is applied only here, at comparison time, on the
            # final output — never earlier in the pipeline. Rounding raw
            # monetary values before comparing them is a classic way to
            # silently hide real divergences.
            if round(abs(legacy_value - erp_value), 2) > DIVERGENCE_TOLERANCE:
                return "value_divergent"

        return "ok"

    merged["status"] = merged.apply(_classify_row, axis=1)
    return merged


def summarize(reference_date: datetime.date, compared_df: pd.DataFrame) -> ReconciliationSummary:
    """Reduce a full comparison DataFrame down to counts an agent (or a
    human skimming a dashboard) can consume without reading every row.
    """
    status_counts = compared_df["status"].value_counts()
    return ReconciliationSummary(
        reference_date=reference_date.isoformat(),
        total_records=len(compared_df),
        missing_in_erp=int(status_counts.get("missing_in_erp", 0)),
        value_divergent=int(status_counts.get("value_divergent", 0)),
        matching=int(status_counts.get("ok", 0)),
    )


def run_reconciliation(reference_date: datetime.date) -> pd.DataFrame:
    """Convenience entry point used by both a CLI/script and the MCP
    server: extract from both systems, compare, and return the full
    annotated DataFrame. Callers decide how much of it to expose.
    """
    legacy_df = extract_legacy_records(reference_date)
    erp_df = extract_erp_records(reference_date)
    return compare(legacy_df, erp_df)
