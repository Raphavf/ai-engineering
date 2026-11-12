"""
api.py

REST front-end over the same ReconciliationService the MCP server uses.

Run:
    uvicorn fiscal_recon.api:app --reload
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException

from fiscal_recon.models import ReconciliationRequest
from fiscal_recon.service import InvalidDateError, ReconciliationService, build_service

app = FastAPI(title="Fiscal Reconciliation API", version="0.2.0")


@lru_cache
def get_service() -> ReconciliationService:
    return build_service()


@app.post("/reconciliation/summary")
def summary(request: ReconciliationRequest, service: ReconciliationService = Depends(get_service)):
    try:
        return service.summary(request.reference_date).model_dump(mode="json")
    except InvalidDateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/reconciliation/branches")
def branches(request: ReconciliationRequest, service: ReconciliationService = Depends(get_service)):
    try:
        items = service.branch_divergences(request.reference_date)
    except InvalidDateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"reference_date": request.reference_date, "divergences": [b.model_dump(mode="json") for b in items]}


@app.get("/health")
def health():
    return {"status": "ok"}
