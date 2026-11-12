"""
mcp_server.py

MCP server exposing ReconciliationService as tools an LLM agent can call.
No business logic here -- only the translation between "what an agent
can ask for" and the service.

Run with the MCP Inspector:
    mcp dev src/fiscal_recon/mcp_server.py
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from fiscal_recon.models import KEY_FIELDS, VALUE_FIELDS
from fiscal_recon.service import ReconciliationService, build_service

INSTRUCTIONS = (
    "Fiscal reconciliation between a legacy source-of-truth system and an ERP. "
    "Start with get_reconciliation_summary for a date, then list_divergent_records "
    "or get_branch_divergences to drill down. Document numbers are pseudonymized: "
    "pass the `document_id` you received to get_record_detail."
)


def build_server(service: ReconciliationService) -> FastMCP:
    mcp = FastMCP(name="fiscal-reconciliation", instructions=INSTRUCTIONS)

    @mcp.tool()
    def get_reconciliation_summary(reference_date: str) -> dict:
        """Aggregated counts for one date: total records, missing in ERP,
        value-divergent, and matching.

        Args:
            reference_date: ISO date (YYYY-MM-DD), before today and within the lookback window.
        """
        return service.summary(reference_date).model_dump(mode="json")

    @mcp.tool()
    def list_divergent_records(reference_date: str, limit: int = 50) -> list[dict]:
        """Records that are missing in the ERP or diverge in value for one date.
        Document numbers are replaced by a pseudonymized `document_id`.

        Args:
            reference_date: ISO date (YYYY-MM-DD).
            limit: maximum number of records to return (1-500).
        """
        limit = max(1, min(limit, 500))
        return service.divergent_records(reference_date, limit=limit)

    @mcp.tool()
    def get_record_detail(
        reference_date: str,
        origin_branch: str,
        destination_branch: str,
        document_id: str,
        series: str,
    ) -> dict:
        """Full comparison detail (legacy values, ERP values, status) for one record.

        Args:
            reference_date: ISO date (YYYY-MM-DD).
            origin_branch: origin branch code.
            destination_branch: destination branch code.
            document_id: pseudonymized id from list_divergent_records.
            series: document series.
        """
        record = service.record_detail(reference_date, origin_branch, destination_branch, document_id, series)
        if record is None:
            return {"found": False, "message": "No record matches this key for the given date."}
        return {"found": True, "record": record}

    @mcp.tool()
    def get_branch_divergences(reference_date: str) -> list[dict]:
        """Divergences rolled up per origin branch, with the percentage gap
        between legacy and ERP totals.

        Args:
            reference_date: ISO date (YYYY-MM-DD).
        """
        return [b.model_dump(mode="json") for b in service.branch_divergences(reference_date)]

    @mcp.tool()
    def explain_reconciliation_rules() -> str:
        """Plain-language description of the business rules applied."""
        return (
            f"Comparison key: {', '.join(KEY_FIELDS)}.\n"
            f"Value fields monitored: {', '.join(VALUE_FIELDS)}.\n"
            "Source of truth: the legacy system (LEFT JOIN from it). Documents only "
            "in the ERP are not reported.\n"
            "Zero tolerance: any difference that survives rounding to cents is a divergence.\n"
            "Dates: must be before today and inside the lookback window."
        )

    return mcp


def main() -> None:
    build_server(build_service()).run()


if __name__ == "__main__":
    main()
