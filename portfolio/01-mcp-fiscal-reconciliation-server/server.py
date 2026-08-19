"""
server.py

MCP server that exposes `reconciliation_service.py` as tools an LLM agent
can call. This file intentionally contains NO business logic of its own —
its only job is to translate between "what an agent can safely ask for"
and "what the reconciliation service already knows how to do".

Run it locally with the MCP Inspector for testing:

    mcp dev server.py

Or run it directly as a stdio server (what a host application like
Claude Desktop actually launches):

    python server.py
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

# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------
# This is the single most important design decision in this file, so it
# gets the longest comment.
#
# An LLM agent doing a multi-step task will often call several tools in a
# row against the SAME underlying data — for example:
#   1. get_reconciliation_summary("2026-06-01")
#   2. list_divergent_records("2026-06-01")
#   3. get_record_detail("2026-06-01", ...)
#
# Without a cache, that's three separate round trips to two different
# production databases for data that hasn't changed between calls. That's
# not just slow — it's the difference between "a tool an agent can use
# freely" and "a tool that makes your DBA nervous every time an agent runs".
#
# A simple in-memory TTL cache, keyed by the query parameters, turns three
# expensive round trips into one. Five minutes is deliberately short: long
# enough to cover one agent conversation, short enough that stale data
# never survives past a single interactive session.
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


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------
# A pandas DataFrame is NOT JSON-serializable as-is: it can contain
# pandas.Timestamp objects, NaN values, and numpy scalar types
# (numpy.int64, numpy.float64, ...) that Python's built-in json module
# doesn't know how to encode. Returning a raw `df.to_dict()` from a tool
# either crashes the MCP call outright or — worse — silently serializes
# into something the model can't actually use.
#
# `_to_json_safe` exists because I hit this exact failure mode in
# production and had to trace it back from "the tool call just breaks"
# to "oh, it's the numpy types".
def _to_json_safe(value):
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if hasattr(value, "item"):  # numpy scalar types expose .item()
        return value.item()
    if pd.isna(value):
        return None
    return value


def _dataframe_to_records(df: pd.DataFrame) -> list[dict]:
    raw_records = df.to_dict(orient="records")
    return [{key: _to_json_safe(val) for key, val in record.items()} for record in raw_records]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
# Each tool corresponds to one real use case, not one database table.
# The goal is that an agent (or a human reading the tool list) can figure
# out which tool to call from its name and docstring alone — the docstring
# IS the interface an LLM sees, so it's written the way you'd write API
# documentation, not the way you'd write an internal code comment.

@mcp.tool()
def get_reconciliation_summary(reference_date: str = "2026-06-01") -> dict:
    """Return the aggregated reconciliation summary between the legacy
    system (source of truth) and the ERP system, starting from a given
    date: total records checked, how many are missing in the ERP, how
    many have a value divergence, and how many match exactly.

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
    mismatch) for a given reference date. Matching records are
    deliberately excluded — an agent asking "what's wrong?" doesn't need
    to read through thousands of rows that are already correct.

    Sensitive identifiers are pseudonymized before being returned.

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
    full comparison detail (legacy values, ERP values, and status).

    Use this after `list_divergent_records` when the agent (or the user
    it's assisting) wants to drill into one particular record instead of
    reading the whole divergent list.
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
    """Explain, in plain language, the business rules this reconciliation
    applies — useful for an agent that needs to answer "why was this
    flagged?" without guessing.
    """
    return (
        f"Comparison key: {', '.join(reconciliation.KEY_FIELDS)}.\n"
        f"Value fields monitored: {', '.join(reconciliation.VALUE_FIELDS)}.\n"
        "Source of truth: the legacy system -- comparison is a LEFT JOIN "
        "starting from it.\n"
        "Zero tolerance: any non-zero numeric divergence is reported.\n"
        "Rounding is applied only to monetary fields, and only at the "
        "final output stage -- never before comparing raw values."
    )


if __name__ == "__main__":
    mcp.run()
