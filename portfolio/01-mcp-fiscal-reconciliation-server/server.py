"""
server.py

MCP server exposing reconciliation_service.py as tools an LLM agent can
call. No business logic lives here -- just the translation layer between
"what an agent can ask for" and the reconciliation service.

Run locally with the MCP Inspector:
    mcp dev server.py
"""

from __future__ import annotations

import datetime
import time

import pandas as pd
from mcp.server.fastmcp import FastMCP

import reconciliation_service as reconciliation
from security.anonymizer import pseudonymize_identifier

mcp = FastMCP(
    name="fiscal-reconciliation",
    instructions=(
        "Server for fiscal reconciliation between a legacy source-of-truth "
        "system and an ERP system. Use the tools to get an aggregated "
        "summary, list divergent records, or look up one specific record."
    ),
)

# In-memory cache, keyed by reference date: avoids re-querying both
# databases when an agent calls multiple tools in a row for the same date.
_CACHE: dict[str, dict] = {}
_CACHE_TTL_SECONDS = 300


def _get_comparison(reference_date_str: str) -> pd.DataFrame:
    """Run (or reuse a cached) reconciliation for a given reference date."""
    now = time.time()
    cached_entry = _CACHE.get(reference_date_str)
    if cached_entry and (now - cached_entry["timestamp"]) < _CACHE_TTL_SECONDS:
        return cached_entry["result"]

    reference_date = datetime.date.fromisoformat(reference_date_str)
    result = reconciliation.run_reconciliation(reference_date)
    _CACHE[reference_date_str] = {"result": result, "timestamp": now}
    return result


def _to_json_safe(value):
    """Convert pandas/numpy types that aren't JSON-serializable on their own."""
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if hasattr(value, "item"):  # numpy scalar types
        return value.item()
    if pd.isna(value):
        return None
    return value


def _dataframe_to_records(df: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame into a list of JSON-safe dicts."""
    raw_records = df.to_dict(orient="records")
    return [{key: _to_json_safe(val) for key, val in record.items()} for record in raw_records]


@mcp.tool()
def get_reconciliation_summary(reference_date: str = "2026-06-01") -> dict:
    """Return the aggregated reconciliation summary for a given date:
    total records, how many are missing in the ERP, how many diverge in
    value, and how many match.

    Args:
        reference_date: cutoff date in ISO format, YYYY-MM-DD.
    """
    compared_df = _get_comparison(reference_date)
    reference = datetime.date.fromisoformat(reference_date)
    summary = reconciliation.summarize(reference, compared_df)
    return summary.__dict__


@mcp.tool()
def list_divergent_records(reference_date: str = "2026-06-01") -> list[dict]:
    """List only the records that diverge (missing in ERP or value
    mismatch) for a given date. Identifiers are pseudonymized before
    being returned.

    Args:
        reference_date: cutoff date in ISO format, YYYY-MM-DD.
    """
    compared_df = _get_comparison(reference_date)
    divergent_df = compared_df[compared_df["status"] != "ok"].copy()
    divergent_df["document_number"] = divergent_df["document_number"].apply(
        pseudonymize_identifier
    )
    return _dataframe_to_records(divergent_df)


@mcp.tool()
def get_record_detail(
    reference_date: str,
    origin_branch: str,
    destination_branch: str,
    document_number: str,
    series: str,
) -> dict:
    """Look up one specific record by its composite key and return its
    full comparison detail (legacy values, ERP values, status).
    """
    compared_df = _get_comparison(reference_date)
    match = compared_df[
        (compared_df["origin_branch"] == origin_branch)
        & (compared_df["destination_branch"] == destination_branch)
        & (compared_df["document_number"] == document_number)
        & (compared_df["series"] == series)
    ]
    if match.empty:
        return {"found": False, "message": "No record matches this key for the given date."}

    records = _dataframe_to_records(match)
    return {"found": True, "record": records[0]}


@mcp.tool()
def explain_reconciliation_rules() -> str:
    """Explain, in plain language, the business rules this reconciliation applies."""
    return (
        f"Comparison key: {', '.join(reconciliation.KEY_FIELDS)}.\n"
        f"Value fields monitored: {', '.join(reconciliation.VALUE_FIELDS)}.\n"
        "Source of truth: the legacy system -- comparison is a LEFT JOIN "
        "starting from it.\n"
        "Zero tolerance: any non-zero numeric divergence is reported.\n"
        "Rounding is applied only to monetary fields, at the final output stage."
    )


if __name__ == "__main__":
    mcp.run()
