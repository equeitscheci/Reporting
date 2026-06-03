# Insightforge Backend

Python (FastAPI) services for the platform:

- `app/connectors` — Connector SDK + REST / JDBC / FlatFile / MCP connectors, auth, retry, CDC.
- `app/canonical` — Canonical (ERP-agnostic) data model + industry extension packs.
- `app/mapping` — Declarative mapping engine (source field → canonical) with transforms.
- `app/pipeline` — Extract → map → validate orchestration primitives + sync state/CDC.
- `app/insights` — Anomaly detection, forecasting, NLQ, prescriptive recommendations.
- `app/core` — Config, multi-tenancy, secrets vault, security/RBAC, registries.
- `app/api` — FastAPI routes (tenants, connectors, metrics, reports, insights).
- `app/cli.py` — `insightforge demo` runs an end-to-end pipeline on bundled sample data.

## Install & run
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run the API
uvicorn app.main:app --reload    # http://localhost:8000/docs

# Run the self-contained demo (no external ERP needed)
python -m app.cli demo --tenant acme-mfg

# Tests
pytest
```

The demo uses the in-memory sample ERP under `app/connectors/sample_data` so the full
extract → map → validate → metrics → insights path runs with zero external dependencies.
