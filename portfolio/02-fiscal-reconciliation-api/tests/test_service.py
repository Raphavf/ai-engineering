"""
tests/test_service.py

Unit tests for the reconciliation logic and the date-window validation
rule. None of these tests touch a real database -- the connector
functions are replaced with mocks via `unittest.mock.patch`, so the
tests run fast and deterministically in CI without any external
dependency.
"""

import datetime
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from src.api import _validate_reference_date
from src.models import BranchBalance
from src.service import reconcile_branches


# ---------------------------------------------------------------------------
# reconcile_branches: patch both connector functions so the service layer
# is tested in isolation from anything database-related.
# ---------------------------------------------------------------------------

@patch("src.service.fetch_erp_balances")
@patch("src.service.fetch_legacy_balances")
def test_reconcile_branches_flags_value_mismatch(mock_fetch_legacy, mock_fetch_erp):
    mock_fetch_legacy.return_value = [
        BranchBalance(branch_code="B001", reference_date="2026-06-01", net_value=1000.0, tax_value=100.0)
    ]
    mock_fetch_erp.return_value = [
        BranchBalance(branch_code="B001", reference_date="2026-06-01", net_value=950.0, tax_value=100.0)
    ]

    result = reconcile_branches("2026-06-01")

    assert len(result) == 1
    assert result[0].branch_code == "B001"
    assert result[0].divergence_percentage == 5.0


@patch("src.service.fetch_erp_balances")
@patch("src.service.fetch_legacy_balances")
def test_reconcile_branches_treats_missing_erp_branch_as_zero(mock_fetch_legacy, mock_fetch_erp):
    mock_fetch_legacy.return_value = [
        BranchBalance(branch_code="B002", reference_date="2026-06-01", net_value=500.0, tax_value=50.0)
    ]
    mock_fetch_erp.return_value = []  # branch never made it into the ERP system

    result = reconcile_branches("2026-06-01")

    assert len(result) == 1
    assert result[0].erp_net_value == 0.0
    assert result[0].divergence_percentage == 100.0


@patch("src.service.fetch_erp_balances")
@patch("src.service.fetch_legacy_balances")
def test_reconcile_branches_returns_nothing_when_values_match(mock_fetch_legacy, mock_fetch_erp):
    mock_fetch_legacy.return_value = [
        BranchBalance(branch_code="B003", reference_date="2026-06-01", net_value=200.0, tax_value=20.0)
    ]
    mock_fetch_erp.return_value = [
        BranchBalance(branch_code="B003", reference_date="2026-06-01", net_value=200.0, tax_value=20.0)
    ]

    result = reconcile_branches("2026-06-01")

    assert result == []


# ---------------------------------------------------------------------------
# _validate_reference_date: boundary-condition tests for the business rule.
# `today` is injected explicitly so these tests never depend on the actual
# calendar date they happen to run on.
# ---------------------------------------------------------------------------

FIXED_TODAY = datetime.date(2026, 6, 15)


def test_validate_reference_date_accepts_valid_date_in_window():
    result = _validate_reference_date("2026-06-01", today=FIXED_TODAY)
    assert result == datetime.date(2026, 6, 1)


def test_validate_reference_date_rejects_today():
    with pytest.raises(HTTPException) as exc_info:
        _validate_reference_date(FIXED_TODAY.isoformat(), today=FIXED_TODAY)
    assert exc_info.value.status_code == 400
    assert "not closed yet" in exc_info.value.detail


def test_validate_reference_date_rejects_future_date():
    future = (FIXED_TODAY + datetime.timedelta(days=1)).isoformat()
    with pytest.raises(HTTPException):
        _validate_reference_date(future, today=FIXED_TODAY)


def test_validate_reference_date_rejects_date_outside_lookback_window():
    too_old = (FIXED_TODAY - datetime.timedelta(days=31)).isoformat()
    with pytest.raises(HTTPException) as exc_info:
        _validate_reference_date(too_old, today=FIXED_TODAY)
    assert "outside the allowed lookback window" in exc_info.value.detail


def test_validate_reference_date_accepts_earliest_boundary_date():
    earliest_allowed = (FIXED_TODAY - datetime.timedelta(days=30)).isoformat()
    result = _validate_reference_date(earliest_allowed, today=FIXED_TODAY)
    assert result == FIXED_TODAY - datetime.timedelta(days=30)


def test_validate_reference_date_rejects_malformed_date():
    with pytest.raises(HTTPException) as exc_info:
        _validate_reference_date("not-a-date", today=FIXED_TODAY)
    assert exc_info.value.status_code == 400
