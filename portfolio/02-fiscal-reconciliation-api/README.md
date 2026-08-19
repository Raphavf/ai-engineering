# Fiscal Reconciliation API

A standalone, testable Python package for the reconciliation logic used by
[`mcp-fiscal-reconciliation-server`](../01-mcp-fiscal-reconciliation-server). This project shows the
same domain problem — comparing fiscal records between a legacy source-of-truth system and an ERP
system — built as a proper `src/` layout package: typed models, connection-pooled connectors, a
FastAPI HTTP layer, and a pytest suite with mocked database calls.

## Why a separate project instead of one big repo

The MCP server in project 01 is the AI-facing layer. This project is the "boring but correct"
foundation it depends on. Keeping them separate (in real life, as separate packages with a version
pin between them) means the reconciliation logic can be tested, versioned, and reused by *anything* —
a CLI script, a scheduled job, a REST API, or an MCP server — without any of those callers needing to
know about each other.

## Structure

```
src/
  config.py                     # pydantic-settings based configuration
  models.py                     # Pydantic v2 domain models
  service.py                    # the reconciliation algorithm
  api.py                        # FastAPI router with business-rule validation
  connectors/
    oracle_connector.py         # pooled legacy-system connector
    sap_hana_connector.py       # ERP-system connector (optional dependency)
tests/
  test_service.py               # unit tests with mocked connectors
```

## What each file teaches

| File | Concept |
|---|---|
| `src/models.py` | Pydantic v2 models, including a **computed property** (`divergence_percentage`) derived from other fields instead of stored redundantly. |
| `src/config.py` | Loading configuration from environment variables with validation, instead of scattering `os.environ.get(...)` calls throughout the codebase. |
| `src/api.py` | A concrete example of **business-rule validation living at the API boundary**: this project enforces a 30-day lookback window (today's data isn't considered "closed" yet, so it's rejected) with a dedicated, testable validation function. |
| `src/connectors/oracle_connector.py` | Lazy connection pool initialization — the pool is created on first real use, not at import time. |
| `tests/test_service.py` | Testing database-dependent code **without** a real database, using `unittest.mock` to replace the connector layer. |

## Running the tests

```bash
pip install -r requirements.txt
pytest -v
```

## Running the API

```bash
uvicorn src.api:app --reload
```
