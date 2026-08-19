"""
src/api.py

FastAPI layer. Its main job beyond routing is enforcing a business rule
that has nothing to do with HTTP: a reconciliation can only be requested
for a date within the last `lookback_window_days` days, and NOT for today
-- today's data isn't considered "closed" yet (transactions can still be
posted for the current day), so reconciling it would just report false
divergences that resolve themselves a few hours later.

This validation deliberately lives in its own testable function
(`_validate_reference_date`) instead of being buried inline in the route
handler, so it can be unit tested directly without spinning up an HTTP
client -- see tests/test_service.py for the boundary-condition tests.
"""

from __future__ import annotations

import datetime

from fastapi import FastAPI, HTTPException

from src.config import settings
from src.models import ReconciliationRequest
from src.service import reconcile_branches

app = FastAPI(title="Fiscal Reconciliation API")


def _validate_reference_date(reference_date_str: str, today: datetime.date | None = None) -> datetime.date:
    """Validate that `reference_date_str` falls within the allowed
    lookback window: strictly before today, and no further back than
    `settings.lookback_window_days`.

    Args:
        reference_date_str: the date to validate, ISO format.
        today: injectable for testing (defaults to the real "today" if
            omitted). This is the fix for a subtle bug: using
            `datetime.date.today()` directly as a function DEFAULT
            argument evaluates it once, at import time, not on every
            call -- so "today" would silently freeze at whatever date the
            server happened to start on. Passing it as a real parameter
            with a runtime default avoids that trap entirely.

    Raises:
        HTTPException: 400 if the date is malformed, today, or outside
            the allowed window.
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
    """Trigger a reconciliation run for a given reference date and return
    the list of divergent branches.
    """
    validated_date = _validate_reference_date(request.reference_date)
    divergences = reconcile_branches(validated_date.isoformat())
    return {"reference_date": validated_date.isoformat(), "divergences": [d.model_dump() for d in divergences]}
