"""
src/api.py

FastAPI layer. Also enforces the business rule that a reconciliation can
only be requested for a date within the allowed lookback window, and not
for today (today's data isn't considered closed yet).
"""

from __future__ import annotations

import datetime

from fastapi import FastAPI, HTTPException

from src.config import settings
from src.models import ReconciliationRequest
from src.service import reconcile_branches

app = FastAPI(title="Fiscal Reconciliation API")


def _validate_reference_date(reference_date_str: str, today: datetime.date | None = None) -> datetime.date:
    """Validate that the date is before today and within the lookback window.

    `today` is a parameter (not just datetime.date.today() used inline)
    so it can be injected in tests instead of depending on the real
    calendar date.
    """
    if today is None:
        today = datetime.date.today()

    try:
        reference_date = datetime.date.fromisoformat(reference_date_str)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="reference_date must be in YYYY-MM-DD format") from exc

    if reference_date >= today:
        raise HTTPException(
            status_code=400,
            detail="reference_date must be before today -- today's data is not closed yet.",
        )

    earliest_allowed = today - datetime.timedelta(days=settings.lookback_window_days)
    if reference_date < earliest_allowed:
        raise HTTPException(
            status_code=400,
            detail=(
                f"reference_date is outside the allowed lookback window "
                f"of {settings.lookback_window_days} days (earliest allowed: {earliest_allowed.isoformat()})."
            ),
        )

    return reference_date


@app.post("/reconciliation")
def run_reconciliation(request: ReconciliationRequest):
    """Trigger a reconciliation run and return the list of divergent branches."""
    validated_date = _validate_reference_date(request.reference_date)
    divergences = reconcile_branches(validated_date.isoformat())
    return {"reference_date": validated_date.isoformat(), "divergences": [d.model_dump() for d in divergences]}
