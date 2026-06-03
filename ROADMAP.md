# Roadmap — MVP vs Phase 2 vs Phase 3

Scope is sliced so every phase ships a *usable* product, not a half-built layer.

## MVP (Phase 1) — "Connect, model, see"
Goal: a tenant connects one ERP, gets a governed canonical model and 2–3 prebuilt dashboards.

**In scope**
- Connector SDK + **REST**, **JDBC/ODBC**, **FlatFile/SFTP** connectors (MCP stubbed).
- Auth: API key + OAuth2 client-credentials; secrets via vault references.
- Incremental sync (high-watermark). CDC for SQL Server/Postgres only.
- Canonical core entities + **Manufacturing** and **Distribution** extension packs.
- Mapping engine (YAML), declarative validation, quarantine.
- Postgres warehouse, star-schema marts via dbt, metrics layer for ~20 core metrics.
- Airflow batch DAG (scheduled). Freshness tracking.
- Metrics API + report execution; **report builder** + 2 prebuilt dashboards
  (Manufacturing job profitability, Distribution inventory turns) + Executive summary.
- Insights: **rule-based anomaly detection** + **baseline forecasting** + explanations.
- Multi-tenant control plane (schema-per-tenant marts, RLS on control), RBAC, audit log.

**Explicitly deferred:** NLQ to be heuristic-only, no real-time, no self-serve connector marketplace.

## Phase 2 — "Insights, real-time, more verticals"
- **NLQ** with LLM → semantic-layer query (whitelisted metrics/dims) + driver analysis.
- Near-real-time ingestion (webhooks/CDC streaming, micro-batch).
- Construction, Field Service, Office Technology extension packs + dashboards.
- ML forecasting (Prophet/boosted trees), prescriptive recommendation rules library.
- Custom metric builder UI; cross-source joins in the builder.
- Snowflake/BigQuery adapters; per-tenant warehouse promotion.
- Connector marketplace + self-serve mapping UI with field-suggestion.

## Phase 3 — "Scale, governance, intelligence"
- Thousands of tenants: warehouse sharding, cost controls, query result cache tiering.
- Data contracts + lineage UI; semantic versioning of metrics.
- Anomaly root-cause graphs; what-if simulation; recommended actions with feedback loop.
- SOC2 Type II controls automation; customer-managed keys (BYOK); data residency.
- Embedded analytics SDK (white-label dashboards in customer apps).

## Sequencing / dependencies
```
Connector SDK ─▶ Mapping ─▶ Canonical ─▶ dbt marts ─▶ Metrics API ─▶ Dashboards
                                   └▶ Validation ─▶ Freshness
Metrics API ─▶ Insights (anomaly/forecast) ─▶ Recommendations ─▶ NLQ
Control plane (tenants/secrets/RBAC) underpins everything (built first).
```

## Success metrics
- Time-to-first-dashboard for a new tenant/ERP: **< 1 day** (mapping file only).
- New ERP onboarded with **zero core code changes** (config only).
- p95 dashboard query latency **< 2s** on cached metrics.
