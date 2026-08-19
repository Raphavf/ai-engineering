# MCP Fiscal Reconciliation Server

An [MCP](https://modelcontextprotocol.io) (Model Context Protocol) server that exposes a real fiscal
reconciliation workflow — comparing records between a legacy "source of truth" system and an ERP
system — as **tools** an LLM agent can call directly.

This project is a generic, anonymized version of a production system I built to reconcile fiscal
notes across a legacy database and SAP. Table names, field names, and business specifics have been
replaced with generic equivalents (`LegacySystem`, `ErpSystem`, `Note`, etc.) so it's safe to publish
publicly, but the architecture and the problems it solves are real.

## Why this exists

Before this project, the reconciliation logic (`reconciliation_service.py`) already existed as a
working script that a human ran manually and read the output of. The goal here was: **let an LLM
agent run it too**, without becoming a liability. That's a different problem than "wrap a function in
a decorator" — an agent can call your tool multiple times in a row, in an order you didn't predict,
and it needs structured, safe, serializable answers every time.

## Architecture

```
LLM Host (Claude, etc.)
      │  MCP protocol (stdio or Streamable HTTP)
      ▼
server.py            <- MCP tool definitions (thin layer, no business logic)
      │
      ▼
reconciliation_service.py   <- the actual comparison logic (pandas)
      │
      ▼
connectors.py         <- pooled DB connections (legacy DB + ERP DB)
```

`security/anonymizer.py` and `security/secrets_manager.py` sit alongside this pipeline: the former
pseudonymizes sensitive identifiers before data is sent anywhere an LLM can see it, and the latter
keeps database credentials out of source control and out of plaintext config files.

## What each file teaches

| File | Concept a reader can learn from it |
|---|---|
| `server.py` | How to expose existing business logic as MCP tools without touching the logic itself; why `DataFrame` objects can't be returned directly over MCP/JSON; why a naive tool wrapper breaks under multi-step agent calls without caching. |
| `reconciliation_service.py` | A realistic "compare two data sources" algorithm: key-based join, tolerance rules, and why *which side is the source of truth* changes your join strategy. |
| `connectors.py` | Connection pooling for two different databases (an Oracle-style legacy system and a SAP HANA-style ERP), and why you don't open a new connection per call. |
| `security/anonymizer.py` | HMAC-based pseudonymization — deterministic (same input always maps to same output, so joins still work) but irreversible without the secret key. |
| `security/secrets_manager.py` | Why credentials should never be hardcoded or committed, and one way (Fernet symmetric encryption + OS credential store) to solve that on a Windows-based production machine. |

## Running it

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your own connection details
mcp dev server.py      # opens the MCP Inspector for local testing
```

## Key design decisions (and why)

- **The MCP layer never touches business logic.** `server.py` only imports and calls
  `reconciliation_service.py`. If the reconciliation rules change, the MCP tools don't need to.
- **In-memory TTL cache.** An agent doing a multi-step task (e.g. "give me the summary, then list the
  problem notes, then show me the detail on note X") would otherwise hit both databases three times
  for the same underlying data. A 5-minute cache turns that into one real query pair.
- **Explicit JSON-safe serialization.** `pandas.Timestamp`, `NaN`, and `numpy.int64` are not
  JSON-serializable. Returning a raw `DataFrame.to_dict()` to an LLM either crashes the tool call or
  silently sends garbage. `_to_json_safe()` exists specifically because I hit this in production.
- **Read-only, bounded queries only.** Every query enforces a date range — no tool here can trigger an
  unbounded `SELECT *` against a production database.
