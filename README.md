# Insightforge — ERP-Agnostic Reporting & Insights Platform

Insightforge is a modular, multi-tenant reporting and insights platform for small-to-mid-sized
businesses. It connects to heterogeneous ERP / CRM / SaaS systems, normalizes their data into a
**canonical semantic model**, runs ELT into a warehouse, and serves **dashboards, ad-hoc reports,
and AI-driven insights** through a configurable UI.

It targets ECI Software Solutions' core verticals: **Manufacturing, Wholesale/Retail Distribution,
Building Supply Distribution, Residential Construction, Field Service, and Office Technology dealers.**

```
ERP / CRM / Files ──▶ Connectors (SDK) ──▶ Mapping Engine ──▶ Canonical Model
                                                                   │
                                                                   ▼
                          Insights Engine ◀── Warehouse (star schema) ◀── ELT Pipeline
                                  │                     │
                                  ▼                     ▼
                          REST/GraphQL API ──▶ React Report Builder + Dashboards
```

## Why it exists
SMBs run on a long tail of vertical ERPs (each with its own schema). They cannot afford a data team.
Insightforge gives them governed metrics and prebuilt industry dashboards with **config over code**:
new ERPs are onboarded by writing a mapping file, not by forking the codebase.

## Repository layout

| Path | Purpose |
|------|---------|
| `ARCHITECTURE.md` | Full system architecture, diagrams, data flow, multi-tenancy |
| `ROADMAP.md` | MVP scope vs Phase 2 / Phase 3 |
| `backend/` | Python (FastAPI) services: connector SDK, mapping, pipeline, insights, API |
| `warehouse/` | Star-schema DDL + dbt models + metrics (semantic) layer |
| `orchestration/` | Airflow DAG example for batch + near-real-time ELT |
| `frontend/` | React + TypeScript report builder and dashboards |
| `config/` | Per-tenant config, connector mappings, metric definitions |

## Quick start

```bash
# 1. Backend (FastAPI) — runnable demo with seeded sample tenant
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
# Open http://localhost:8000/docs

# 2. Run the end-to-end demo pipeline (no external ERP required)
python -m app.cli demo --tenant acme-mfg

# 3. Tests
pytest -q

# 4. Full stack with warehouse + orchestration + UI
docker compose up --build
```

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the deep dive and [`ROADMAP.md`](./ROADMAP.md) for scope.

## Design principles
1. **ERP-agnostic abstraction first** — code targets the canonical model, never a vendor schema.
2. **Industry-aware, not hardcoded** — verticals are plugins/extension packs.
3. **Config over code** — connectors, mappings, metrics, and dashboards are declarative.
4. **Scalable to thousands of SMB tenants** — pooled multi-tenancy with row-level isolation.
5. **Secure & SOC2-ready** — secrets vault, audit log, RBAC, per-tenant data boundaries.
