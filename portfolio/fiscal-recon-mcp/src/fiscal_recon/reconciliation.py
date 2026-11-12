"""
reconciliation.py

Pure comparison logic: no database, MCP or HTTP code here, so it can be
tested and reused on its own.

- LEGACY system: source of truth
- ERP system: should mirror the legacy data; mismatches get flagged
"""

from __future__ import annotations

import datetime

import pandas as pd

from fiscal_recon.models import (
    KEY_FIELDS,
    VALUE_FIELDS,
    BranchDivergence,
    FiscalRecord,
    ReconciliationSummary,
)
from fiscal_recon.sources.base import RecordSource

# Zero tolerance: any difference that survives rounding to cents is a divergence
DIVERGENCE_TOLERANCE = 0.0

_COLUMNS = [*KEY_FIELDS, "issue_date", *VALUE_FIELDS]


def records_to_frame(records: list[FiscalRecord]) -> pd.DataFrame:
    """Build a DataFrame with stable columns, even when the list is empty."""
    return pd.DataFrame([r.model_dump() for r in records], columns=_COLUMNS)


def compare(legacy_df: pd.DataFrame, erp_df: pd.DataFrame) -> pd.DataFrame:
    """Left-join legacy vs ERP records and classify each row's status."""
    merged = legacy_df.merge(
        erp_df.drop(columns=["issue_date"], errors="ignore"),
        on=KEY_FIELDS,
        how="left",
        suffixes=("_legacy", "_erp"),
    )

    if merged.empty:
        merged["status"] = pd.Series(dtype="object")
        return merged

    missing = merged[f"{VALUE_FIELDS[0]}_erp"].isna()
    divergent = pd.Series(False, index=merged.index)
    for field in VALUE_FIELDS:
        diff = (merged[f"{field}_legacy"] - merged[f"{field}_erp"]).abs().round(2)
        divergent |= diff > DIVERGENCE_TOLERANCE

    merged["status"] = "ok"
    merged.loc[divergent, "status"] = "value_divergent"
    merged.loc[missing, "status"] = "missing_in_erp"
    return merged


def summarize(reference_date: datetime.date, compared_df: pd.DataFrame) -> ReconciliationSummary:
    """Reduce a full comparison DataFrame down to aggregate counts."""
    counts = compared_df["status"].value_counts()
    return ReconciliationSummary(
        reference_date=reference_date,
        total_records=len(compared_df),
        missing_in_erp=int(counts.get("missing_in_erp", 0)),
        value_divergent=int(counts.get("value_divergent", 0)),
        matching=int(counts.get("ok", 0)),
    )


def aggregate_by_branch(reference_date: datetime.date, compared_df: pd.DataFrame) -> list[BranchDivergence]:
    """Roll divergent documents up to their origin branch.

    Missing ERP values count as zero, so a document absent from the ERP
    shows up as its full legacy value in the branch difference.
    """
    divergent = compared_df[compared_df["status"] != "ok"]
    if divergent.empty:
        return []

    grouped = (
        divergent.assign(net_value_erp=divergent["net_value_erp"].fillna(0.0))
        .groupby("origin_branch")
        .agg(
            divergent_documents=("document_number", "count"),
            legacy_net_value=("net_value_legacy", "sum"),
            erp_net_value=("net_value_erp", "sum"),
        )
        .reset_index()
    )
    return [
        BranchDivergence(
            branch_code=row.origin_branch,
            reference_date=reference_date,
            divergent_documents=int(row.divergent_documents),
            legacy_net_value=round(float(row.legacy_net_value), 2),
            erp_net_value=round(float(row.erp_net_value), 2),
        )
        for row in grouped.itertuples()
    ]


def run_reconciliation(
    reference_date: datetime.date, legacy: RecordSource, erp: RecordSource
) -> pd.DataFrame:
    """Extract from both systems, compare, and return the annotated DataFrame."""
    legacy_df = records_to_frame(legacy.fetch_records(reference_date))
    erp_df = records_to_frame(erp.fetch_records(reference_date))
    return compare(legacy_df, erp_df)
