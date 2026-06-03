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

## Optional ECI AI Studio agent

The **Insights → Ask a question** flow works locally by default: the backend parses the question,
runs governed semantic metric queries, and returns a deterministic answer. To delegate that answer
composition to an ECI AI Studio agent, configure the backend with:

```bash
INSIGHTFORGE_AI_STUDIO_AGENT_URL=https://...
INSIGHTFORGE_AI_STUDIO_API_KEY=...
INSIGHTFORGE_AI_STUDIO_AGENT_ID=...
```

When configured, `POST /insights/ask` sends the tenant id, question, local governed answer, and
metric catalog to the agent. If the agent is unavailable or not configured, the endpoint falls back
to the local semantic NLQ answer so the interface remains testable.

## ECI AI Studio widget

The React UI also loads the ECI AI Studio CDN widget in floating-action-button mode:

```html
<script src="https://global-ui.ecinexus.com/eci-ui-cdn-assets/ai-elements/latest/bootstrap.js"></script>
```

The widget is mounted by `frontend/src/components/ECIAgentWidget.tsx` with these default public
values:

```bash
VITE_ECI_AI_WIDGET_BASE_URL=https://ai-api.ecinexus.com
VITE_ECI_AI_WIDGET_INTEGRATION_ID=3875399b-3089-4239-9d86-9ec7d5d98c91
VITE_ECI_AI_WIDGET_AGENT_ID=1fce2ec2-9097-424f-b5b2-f5ea430a248d
VITE_ECI_AI_WIDGET_MODE=fab
VITE_ECI_AI_WIDGET_TOKEN_ENDPOINT=/api/.ai/token
```

The frontend never stores token-exchange secrets. The widget calls `GET /api/.ai/token`, which
proxies to the backend route `GET /.ai/token`. Configure the backend token broker with either:

```bash
# Preferred for real environments
INSIGHTFORGE_AI_WIDGET_TOKEN_URL=https://...
INSIGHTFORGE_AI_WIDGET_CLIENT_ID=...
INSIGHTFORGE_AI_WIDGET_CLIENT_SECRET=...
INSIGHTFORGE_AI_WIDGET_SCOPE=...
INSIGHTFORGE_AI_WIDGET_AUDIENCE=...
```

or, for a short-lived local demo only:

```bash
INSIGHTFORGE_AI_WIDGET_ACCESS_TOKEN=...
```

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the deep dive and [`ROADMAP.md`](./ROADMAP.md) for scope.

## Design principles
1. **ERP-agnostic abstraction first** — code targets the canonical model, never a vendor schema.
2. **Industry-aware, not hardcoded** — verticals are plugins/extension packs.
3. **Config over code** — connectors, mappings, metrics, and dashboards are declarative.
4. **Scalable to thousands of SMB tenants** — pooled multi-tenancy with row-level isolation.
5. **Secure & SOC2-ready** — secrets vault, audit log, RBAC, per-tenant data boundaries.
