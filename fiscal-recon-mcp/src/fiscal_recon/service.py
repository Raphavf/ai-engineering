"""
service.py

ReconciliationService: the one object both the MCP server and the REST
API talk to. Owns the record sources, the cache, date validation and
pseudonymization, so the two front-ends can't drift apart.
"""

from __future__ import annotations

import datetime
from typing import Any, Callable

import pandas as pd

from fiscal_recon import reconciliation
from fiscal_recon.cache import TTLCache
from fiscal_recon.config import Settings
from fiscal_recon.models import BranchDivergence, ReconciliationSummary
from fiscal_recon.security.anonymizer import Pseudonymizer
from fiscal_recon.sources.base import RecordSource


class InvalidDateError(ValueError):
    """Reference date is malformed or outside the allowed window."""


class ReconciliationService:
    def __init__(
        self,
        legacy: RecordSource,
        erp: RecordSource,
        pseudonymizer: Pseudonymizer,
        cache_ttl_seconds: float = 300,
        lookback_window_days: int = 30,
        today: Callable[[], datetime.date] = datetime.date.today,
    ):
        self.legacy = legacy
        self.erp = erp
        self._pseudo = pseudonymizer
        self._cache: TTLCache[pd.DataFrame] = TTLCache(cache_ttl_seconds)
        self._lookback = lookback_window_days
        self._today = today

    # ---- validation -------------------------------------------------

    def validate_date(self, reference_date: str) -> datetime.date:
        """Must be ISO, before today (today isn't closed yet) and inside the lookback window."""
        try:
            parsed = datetime.date.fromisoformat(reference_date)
        except (TypeError, ValueError) as exc:
            raise InvalidDateError("reference_date must be in YYYY-MM-DD format.") from exc

        today = self._today()
        if parsed >= today:
            raise InvalidDateError("reference_date must be before today -- today's data is not closed yet.")
        earliest = today - datetime.timedelta(days=self._lookback)
        if parsed < earliest:
            raise InvalidDateError(
                f"reference_date is outside the {self._lookback}-day lookback window "
                f"(earliest allowed: {earliest.isoformat()})."
            )
        return parsed

    # ---- core -------------------------------------------------------

    def _comparison(self, reference_date: datetime.date) -> pd.DataFrame:
        return self._cache.get_or_compute(
            reference_date,
            lambda: reconciliation.run_reconciliation(reference_date, self.legacy, self.erp),
        )

    def summary(self, reference_date: str) -> ReconciliationSummary:
        date = self.validate_date(reference_date)
        return reconciliation.summarize(date, self._comparison(date))

    def divergent_records(self, reference_date: str, limit: int = 100) -> list[dict[str, Any]]:
        """Divergent rows with document numbers pseudonymized. Capped to keep tool output small."""
        date = self.validate_date(reference_date)
        df = self._comparison(date)
        divergent = df[df["status"] != "ok"].head(limit)
        return [self._public_record(row) for row in divergent.to_dict(orient="records")]

    def record_detail(
        self, reference_date: str, origin_branch: str, destination_branch: str, document_id: str, series: str
    ) -> dict[str, Any] | None:
        """Look up one record by the pseudonymized `document_id` returned by divergent_records."""
        date = self.validate_date(reference_date)
        df = self._comparison(date)
        candidates = df[
            (df["origin_branch"] == origin_branch)
            & (df["destination_branch"] == destination_branch)
            & (df["series"] == series)
        ]
        for row in candidates.to_dict(orient="records"):
            if self._pseudo.pseudonymize(row["document_number"]) == document_id:
                return self._public_record(row)
        return None

    def branch_divergences(self, reference_date: str) -> list[BranchDivergence]:
        date = self.validate_date(reference_date)
        return reconciliation.aggregate_by_branch(date, self._comparison(date))

    # ---- helpers ----------------------------------------------------

    def _public_record(self, row: dict[str, Any]) -> dict[str, Any]:
        """JSON-safe copy of a row with the raw document number replaced."""
        out: dict[str, Any] = {}
        for key, value in row.items():
            if key == "document_number":
                out["document_id"] = self._pseudo.pseudonymize(value)
                continue
            if isinstance(value, (datetime.date, datetime.datetime)):
                value = value.isoformat()
            elif hasattr(value, "item"):  # numpy scalar
                value = value.item()
            if isinstance(value, float) and pd.isna(value):
                value = None
            out[key] = value
        return out


def build_service(settings: Settings | None = None) -> ReconciliationService:
    """Wire sources from settings. Used by the MCP server and API entry points."""
    settings = settings or Settings()

    if settings.backend == "sqlite":
        from fiscal_recon.sources.sqlite import SqliteSource

        legacy = SqliteSource("legacy", settings.sqlite_path, "legacy_fiscal_documents")
        erp = SqliteSource("erp", settings.sqlite_path, "erp_fiscal_documents")
    else:
        from fiscal_recon.security.secrets_manager import SecretsManager
        from fiscal_recon.sources.hana import HanaSource
        from fiscal_recon.sources.oracle import OracleSource

        secrets = SecretsManager(settings.encrypted_credentials_path)
        lc = secrets.get_credentials("legacy_system")
        ec = secrets.get_credentials("erp_system")
        legacy = OracleSource(lc.username, lc.password, lc.dsn)
        erp = HanaSource(ec.host, ec.port, ec.username, ec.password)

    return ReconciliationService(
        legacy,
        erp,
        Pseudonymizer.from_env(),
        cache_ttl_seconds=settings.cache_ttl_seconds,
        lookback_window_days=settings.lookback_window_days,
    )
