"""Pool, cache, security and adapter tests."""

import datetime
import threading

import pytest
from cryptography.fernet import Fernet

from fiscal_recon.cache import TTLCache
from fiscal_recon.security.anonymizer import Pseudonymizer
from fiscal_recon.security.secrets_manager import SecretsManager
from fiscal_recon.sources.base import RecordSource
from fiscal_recon.sources.hana import HanaSource
from fiscal_recon.sources.pool import PoolExhaustedError, SimpleConnectionPool
from fiscal_recon.sources.sqlite import SqliteSource

# ---- pool -------------------------------------------------------------


class FakeConn:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_pool_reuses_connections():
    pool = SimpleConnectionPool(FakeConn, max_size=2)
    with pool.connection() as a:
        pass
    with pool.connection() as b:
        pass
    assert a is b and pool.size == 1


def test_pool_blocks_then_times_out_when_exhausted():
    pool = SimpleConnectionPool(FakeConn, max_size=1, timeout=0.05)
    with pool.connection():
        with pytest.raises(PoolExhaustedError):
            with pool.connection():
                pass


def test_pool_hands_released_connection_to_waiting_thread():
    pool = SimpleConnectionPool(FakeConn, max_size=1, timeout=2)
    got = []
    with pool.connection() as first:
        t = threading.Thread(target=lambda: got.append(pool._acquire()))
        t.start()
    t.join()
    assert got == [first]


def test_pool_discards_connection_that_raised():
    pool = SimpleConnectionPool(FakeConn, max_size=1)
    with pytest.raises(RuntimeError):
        with pool.connection() as broken:
            raise RuntimeError("driver error")
    assert broken.closed and pool.size == 0
    with pool.connection() as fresh:
        assert fresh is not broken


def test_pool_rejects_zero_size():
    with pytest.raises(ValueError):
        SimpleConnectionPool(FakeConn, max_size=0)


# ---- cache ------------------------------------------------------------


def test_cache_expires_after_ttl():
    now = [0.0]
    cache = TTLCache(ttl_seconds=10, clock=lambda: now[0])
    calls = []
    compute = lambda: calls.append(1) or len(calls)  # noqa: E731
    assert cache.get_or_compute("k", compute) == 1
    now[0] = 9.9
    assert cache.get_or_compute("k", compute) == 1
    now[0] = 10.0
    assert cache.get_or_compute("k", compute) == 2


def test_cache_evicts_oldest_when_full():
    now = [0.0]
    cache = TTLCache(ttl_seconds=100, max_entries=2, clock=lambda: now[0])
    for i, key in enumerate("abc"):
        now[0] = i
        cache.get_or_compute(key, lambda: key)
    assert set(cache._data) == {"b", "c"}


# ---- security ---------------------------------------------------------


def test_pseudonymizer_is_deterministic_and_keyed():
    a, b = Pseudonymizer("k" * 16), Pseudonymizer("j" * 16)
    assert a.pseudonymize("123") == a.pseudonymize("123")
    assert a.pseudonymize("123") != b.pseudonymize("123")
    assert "123" not in a.pseudonymize("123")


def test_pseudonymizer_rejects_short_key():
    with pytest.raises(ValueError):
        Pseudonymizer("short")


def test_pseudonymizer_from_env(monkeypatch):
    monkeypatch.delenv("ANONYMIZER_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError):
        Pseudonymizer.from_env()
    monkeypatch.setenv("ANONYMIZER_SECRET_KEY", "x" * 32)
    assert Pseudonymizer.from_env().pseudonymize("1")


def test_secrets_manager_decrypts_and_hides_password(tmp_path):
    key = Fernet.generate_key()
    path = tmp_path / "credentials.enc"
    path.write_bytes(Fernet(key).encrypt(b'{"erp_system": {"username": "u", "password": "s3cret", "host": "h"}}'))
    creds = SecretsManager(path, key_loader=lambda: key).get_credentials("erp_system")
    assert creds.password == "s3cret"
    assert "s3cret" not in repr(creds)


def test_secrets_manager_unknown_system(tmp_path):
    key = Fernet.generate_key()
    path = tmp_path / "c.enc"
    path.write_bytes(Fernet(key).encrypt(b"{}"))
    with pytest.raises(KeyError):
        SecretsManager(path, key_loader=lambda: key).get_credentials("legacy_system")


# ---- adapters ---------------------------------------------------------


def test_sources_satisfy_protocol(synthetic):
    path, *_ = synthetic
    assert isinstance(SqliteSource("x", path, "legacy_fiscal_documents"), RecordSource)


def test_sqlite_rejects_unsafe_table_name(tmp_path):
    with pytest.raises(ValueError):
        SqliteSource("x", tmp_path / "db", "docs; DROP TABLE x")


class FakeHanaCursor:
    def __init__(self, rows, log):
        self._rows, self._log = rows, log

    def execute(self, sql, params):
        self._log.append((sql, params))

    def fetchall(self):
        return self._rows

    def close(self):
        pass


class FakeHanaConn(FakeConn):
    def __init__(self, rows, log):
        super().__init__()
        self._rows, self._log = rows, log

    def cursor(self):
        return FakeHanaCursor(self._rows, self._log)


def test_hana_source_maps_rows_and_binds_date():
    day = datetime.date(2026, 6, 1)
    log = []
    rows = [("B001", "B002", 555, "1", day, "100.50", 18)]
    source = HanaSource("h", 0, "u", "p", connect=lambda: FakeHanaConn(rows, log))
    [record] = source.fetch_records(day)
    assert record.document_number == "555" and record.net_value == 100.5
    assert log[0][1] == (day,) and "?" in log[0][0]  # parameterized, not string-formatted
