"""
reconciliation_service.py

Compares fiscal records between two systems:
- LEGACY SYSTEM: source of truth
- ERP SYSTEM: should mirror the legacy data; mismatches get flagged

No MCP/LLM code here -- just the comparison logic, so it can be tested
and reused on its own (see server.py for the MCP-facing layer).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

import pandas as pd

# Composite key used to match records across both systems
KEY_FIELDS = ["origin_branch", "destination_branch", "document_number", "series"]

# Numeric columns being compared
VALUE_FIELDS = ["net_value", "tax_value"]

# Zero tolerance: any non-zero difference counts as a divergence
DIVERGENCE_TOLERANCE = 0.0


@dataclass
class ReconciliationSummary:
    """Aggregated result of one reconciliation run."""

    reference_date: str
    total_records: int
    missing_in_erp: int
    value_divergent: int
    matching: int


def extract_legacy_records(reference_date: datetime.date) -> pd.DataFrame:
    """Pull records from the legacy system for the given date."""
    raise NotImplementedError("Wire this up to connectors.get_legacy_connection().")


def extract_erp_records(reference_date: datetime.date) -> pd.DataFrame:
    """Pull the equivalent records from the ERP system."""
    raise NotImplementedError("Wire this up to connectors.get_erp_connection().")


def compare(legacy_df: pd.DataFrame, erp_df: pd.DataFrame) -> pd.DataFrame:
    """Left-join legacy vs ERP records and classify each row's status."""
    merged = legacy_df.merge(
        erp_df,
        on=KEY_FIELDS,
        how="left",
        suffixes=("_legacy", "_erp"),
    )

    def _classify_row(row: pd.Series) -> str:
        # No match found in the ERP export at all
        if pd.isna(row.get(f"{VALUE_FIELDS[0]}_erp")):
            return "missing_in_erp"

        for field in VALUE_FIELDS:
            legacy_value = row[f"{field}_legacy"]
            erp_value = row[f"{field}_erp"]
            if round(abs(legacy_value - erp_value), 2) > DIVERGENCE_TOLERANCE:
                return "value_divergent"

        return "ok"

    merged["status"] = merged.apply(_classify_row, axis=1)
    return merged


def summarize(reference_date: datetime.date, compared_df: pd.DataFrame) -> ReconciliationSummary:
    """Reduce a full comparison DataFrame down to aggregate counts."""
    status_counts = compared_df["status"].value_counts()
    return ReconciliationSummary(
        reference_date=reference_date.isoformat(),
        total_records=len(compared_df),
        missing_in_erp=int(status_counts.get("missing_in_erp", 0)),
        value_divergent=int(status_counts.get("value_divergent", 0)),
        matching=int(status_counts.get("ok", 0)),
    )


def run_reconciliation(reference_date: datetime.date) -> pd.DataFrame:
    """Extract from both systems, compare, and return the annotated DataFrame."""
    legacy_df = extract_legacy_records(reference_date)
    erp_df = extract_erp_records(reference_date)
    return compare(legacy_df, erp_df)
