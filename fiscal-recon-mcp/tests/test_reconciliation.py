import datetime

import pandas as pd

from fiscal_recon.models import FiscalRecord
from fiscal_recon.reconciliation import aggregate_by_branch, compare, records_to_frame, summarize

D = datetime.date(2026, 6, 1)


def rec(doc="1", net=100.0, tax=18.0, origin="B001", dest="B002", series="1"):
    return FiscalRecord(
        origin_branch=origin, destination_branch=dest, document_number=doc,
        series=series, issue_date=D, net_value=net, tax_value=tax,
    )


def statuses(legacy, erp):
    df = compare(records_to_frame(legacy), records_to_frame(erp))
    return dict(zip(df["document_number"], df["status"]))


def test_matching_record_is_ok():
    assert statuses([rec()], [rec()]) == {"1": "ok"}


def test_missing_in_erp():
    assert statuses([rec("1"), rec("2")], [rec("1")]) == {"1": "ok", "2": "missing_in_erp"}


def test_one_cent_difference_is_divergent():
    assert statuses([rec(net=100.00)], [rec(net=100.01)]) == {"1": "value_divergent"}


def test_float_noise_below_a_cent_is_not_divergent():
    assert statuses([rec(net=0.1 + 0.2)], [rec(net=0.3)]) == {"1": "ok"}


def test_tax_only_divergence_is_detected():
    assert statuses([rec(tax=18.0)], [rec(tax=7.2)]) == {"1": "value_divergent"}


def test_erp_only_records_are_ignored():
    """Legacy is the source of truth: extra ERP documents are not reported."""
    assert statuses([rec("1")], [rec("1"), rec("99")]) == {"1": "ok"}


def test_same_document_number_different_series_are_distinct():
    legacy = [rec("1", series="1"), rec("1", series="2", net=50.0)]
    erp = [rec("1", series="1")]
    df = compare(records_to_frame(legacy), records_to_frame(erp))
    assert sorted(df["status"]) == ["missing_in_erp", "ok"]


def test_empty_inputs_return_empty_frame_with_status():
    df = compare(records_to_frame([]), records_to_frame([]))
    assert df.empty and "status" in df.columns
    assert summarize(D, df).total_records == 0


def test_summary_counts():
    df = compare(
        records_to_frame([rec("1"), rec("2"), rec("3", net=10.0)]),
        records_to_frame([rec("1"), rec("3", net=11.0)]),
    )
    s = summarize(D, df)
    assert (s.total_records, s.matching, s.missing_in_erp, s.value_divergent) == (3, 1, 1, 1)


def test_branch_aggregation_treats_missing_as_zero():
    df = compare(
        records_to_frame([rec("1", net=1000.0), rec("2", net=500.0, origin="B003")]),
        records_to_frame([rec("1", net=950.0)]),
    )
    by_branch = {b.branch_code: b for b in aggregate_by_branch(D, df)}
    assert by_branch["B001"].divergence_percentage == 5.0
    assert by_branch["B003"].erp_net_value == 0.0
    assert by_branch["B003"].divergence_percentage == 100.0


def test_branch_aggregation_empty_when_all_match():
    df = compare(records_to_frame([rec()]), records_to_frame([rec()]))
    assert aggregate_by_branch(D, df) == []
