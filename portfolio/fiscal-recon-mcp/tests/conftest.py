from __future__ import annotations

import datetime

import pytest

from fiscal_recon.security.anonymizer import Pseudonymizer
from fiscal_recon.service import ReconciliationService
from fiscal_recon.sources.sqlite import SqliteSource
from fiscal_recon.synthetic import generate, write_sqlite

TODAY = datetime.date(2026, 6, 10)
DATES = [datetime.date(2026, 6, 8), datetime.date(2026, 6, 9)]
TEST_KEY = "test-key-0123456789abcdef"


@pytest.fixture(scope="session")
def synthetic(tmp_path_factory):
    legacy, erp, truth = generate(DATES, docs_per_day=300, seed=7)
    path = tmp_path_factory.mktemp("db") / "synthetic.db"
    write_sqlite(path, legacy, erp)
    return path, legacy, erp, truth


@pytest.fixture
def pseudonymizer():
    return Pseudonymizer(TEST_KEY)


@pytest.fixture
def service(synthetic, pseudonymizer):
    path, *_ = synthetic
    return ReconciliationService(
        SqliteSource("legacy", path, "legacy_fiscal_documents"),
        SqliteSource("erp", path, "erp_fiscal_documents"),
        pseudonymizer,
        today=lambda: TODAY,
    )
