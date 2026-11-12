import datetime

import pytest

from fiscal_recon.service import InvalidDateError
from tests.conftest import DATES, TODAY


def _truth_for(truth, legacy, date):
    keys_on_date = {
        (r.origin_branch, r.destination_branch, r.document_number, r.series)
        for r in legacy if r.issue_date == date
    }
    return truth.missing_in_erp & keys_on_date, truth.value_divergent & keys_on_date


@pytest.mark.parametrize("date", DATES)
def test_summary_matches_ground_truth(service, synthetic, date):
    _, legacy, _, truth = synthetic
    missing, divergent = _truth_for(truth, legacy, date)
    s = service.summary(date.isoformat())
    assert s.total_records == 300
    assert s.missing_in_erp == len(missing)
    assert s.value_divergent == len(divergent)
    assert s.matching == 300 - len(missing) - len(divergent)


def test_divergent_records_never_expose_raw_document_numbers(service, synthetic):
    _, legacy, _, _ = synthetic
    raw_numbers = {r.document_number for r in legacy}
    records = service.divergent_records(DATES[0].isoformat())
    assert records
    for r in records:
        assert "document_number" not in r
        assert r["document_id"] not in raw_numbers


def test_divergent_records_respects_limit(service):
    assert len(service.divergent_records(DATES[0].isoformat(), limit=3)) == 3


def test_detail_lookup_round_trips_from_list_output(service):
    """The id an agent gets from list_divergent_records must work in record_detail."""
    first = service.divergent_records(DATES[0].isoformat())[0]
    detail = service.record_detail(
        DATES[0].isoformat(), first["origin_branch"], first["destination_branch"],
        first["document_id"], first["series"],
    )
    assert detail == first


def test_detail_returns_none_for_unknown_id(service):
    first = service.divergent_records(DATES[0].isoformat())[0]
    assert service.record_detail(
        DATES[0].isoformat(), first["origin_branch"], first["destination_branch"], "nope", first["series"]
    ) is None


def test_missing_records_serialize_erp_values_as_null(service):
    missing = [r for r in service.divergent_records(DATES[0].isoformat(), limit=500)
               if r["status"] == "missing_in_erp"]
    assert missing and all(r["net_value_erp"] is None for r in missing)


def test_results_are_cached_per_date(service, monkeypatch):
    calls = []
    original = service.legacy.fetch_records
    monkeypatch.setattr(service.legacy, "fetch_records", lambda d: calls.append(d) or original(d))
    service.summary(DATES[0].isoformat())
    service.divergent_records(DATES[0].isoformat())
    service.branch_divergences(DATES[0].isoformat())
    assert len(calls) == 1


@pytest.mark.parametrize(
    "value, message",
    [
        ("2026/06/01", "YYYY-MM-DD"),
        ("not-a-date", "YYYY-MM-DD"),
        (TODAY.isoformat(), "before today"),
        ((TODAY + datetime.timedelta(days=3)).isoformat(), "before today"),
        ((TODAY - datetime.timedelta(days=31)).isoformat(), "lookback"),
    ],
)
def test_date_validation(service, value, message):
    with pytest.raises(InvalidDateError, match=message):
        service.summary(value)


def test_lookback_boundary_is_inclusive(service):
    edge = (TODAY - datetime.timedelta(days=30)).isoformat()
    assert service.summary(edge).total_records == 0  # valid date, just no data
