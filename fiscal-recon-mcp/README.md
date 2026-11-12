# fiscal-recon-mcp

An MCP server and REST API that let LLM agents reconcile fiscal documents between a legacy source-of-truth system and an ERP. Every system sits behind a small adapter interface. Document numbers are pseudonymized before they reach the model.

The project grew out of several years of reconciling fiscal data across multiple ERPs in retail. **This repository contains no proprietary code, schemas or data.** Everything runs on a seeded synthetic dataset.

## What it does

| MCP tool | Purpose |
|---|---|
| `get_reconciliation_summary` | Counts for a date: total, missing in ERP, value-divergent, matching |
| `list_divergent_records` | Divergent documents, with pseudonymized `document_id` |
| `get_record_detail` | Drill into one document using the `document_id` from the list |
| `get_branch_divergences` | Roll-up per origin branch with % gap |
| `explain_reconciliation_rules` | Business rules in plain language |

The same `ReconciliationService` also backs a FastAPI app (`/reconciliation/summary`, `/reconciliation/branches`). Both front-ends share one validation path and one cache.

## Architecture

```
          MCP client / agent              HTTP client
                 │                             │
          mcp_server.py                     api.py
                 └──────────┬──────────────────┘
                   ReconciliationService
         (date rules · TTL cache · pseudonymization)
                            │
                    reconciliation.py   ← pure pandas logic
                            │
              RecordSource protocol (sources/base.py)
          ┌─────────────┬──────────────┬─────────────┐
     OracleSource   HanaSource    SqliteSource   (next: TOTVS …)
     oracledb pool  bounded pool  synthetic data
```

**Business rules**
- The legacy system is the source of truth (LEFT JOIN from it).
- Zero tolerance: any difference that survives rounding to cents counts as a divergence.
- Today's date is rejected because the day isn't closed yet. Dates must also fall within the lookback window.

**Security**
- Credentials are stored in a Fernet-encrypted file. The key lives in the OS keyring.
- Document numbers are HMAC-pseudonymized and never returned raw. The `document_id` from one tool works as input to the next.
- `DatabaseCredentials.__repr__` never prints the password.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # set ANONYMIZER_SECRET_KEY
fiscal-recon-seed --days 7      # writes data/synthetic.db
pytest                          # unit + MCP end-to-end tests
mcp dev src/fiscal_recon/mcp_server.py   # MCP Inspector
uvicorn fiscal_recon.api:app --reload    # REST API
```

### Local LLM host (no paid API)

```bash
ollama pull qwen2.5:7b
pip install -e ".[host]"
python host/host.py
```

### Oracle integration (optional)

```bash
docker compose up -d oracle
pip install -e ".[oracle]"
python scripts/seed_oracle.py
pytest -m integration
```

SAP HANA has no lightweight free container. `HanaSource` is covered by unit tests with an injected fake connection.

## Tests

The suite runs against a seeded synthetic dataset with **known ground truth**: the generator records exactly which documents it made missing or divergent, and the tests assert the reconciliation finds those and only those. The MCP tests go through a real client session (in-memory transport) and exercise the list → detail flow an agent actually follows.

## Roadmap

- [ ] Oracle integration tests in CI (service container)
- [ ] TOTVS adapter, to prove the adapter interface with a third ERP
- [ ] **Agent eval harness:** measure tool choice, argument correctness and final-answer accuracy against synthetic ground truth, across models
- [ ] MCP resources (schemas, reports) and prompts for common audit workflows
- [ ] Structured logging and OpenTelemetry traces per tool call
- [ ] Optional Redis cache for multi-instance deployments
