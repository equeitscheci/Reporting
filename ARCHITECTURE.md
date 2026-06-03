# Insightforge — System Architecture

This document is the technical reference for the platform. It is intentionally implementation-oriented:
every layer described here maps to code in this repository.

---

## 1. High-level architecture

```
                                ┌──────────────────────────────────────────────┐
                                │                  CONTROL PLANE                 │
                                │  (tenant registry, secrets vault, RBAC,       │
                                │   connector configs, mappings, metric defs)   │
                                └───────────────┬──────────────────────────────┘
                                                │ config (declarative)
 SOURCES                  INGESTION             ▼              MODELING                SERVING
┌──────────┐        ┌─────────────────┐  ┌──────────────┐  ┌─────────────────┐  ┌──────────────────┐
│ ERP REST │──┐     │ Connector SDK   │  │ Mapping      │  │ Warehouse        │  │ REST / GraphQL    │
│ SQL DBs  │──┼────▶│  - REST         │─▶│  Engine      │─▶│  - Raw (bronze)  │─▶│ Metrics API       │
│ Flat/SFTP│──┤     │  - JDBC/ODBC    │  │ (field map + │  │  - Canonical     │  │                   │
│ MCP tools│──┘     │  - FlatFile     │  │  transforms +│  │    (silver)      │  │ Insights API      │
│ CRM/SaaS │        │  - MCP adapter  │  │  validation) │  │  - Marts/star    │  │ (anomaly, NLQ,    │
└──────────┘        └────────┬────────┘  └──────────────┘  │    (gold)        │  │  forecast, recs)  │
                             │ extract (incremental/CDC)    └────────┬────────┘  └────────┬─────────┘
                             ▼                                       │ dbt transforms     │
                    ┌─────────────────┐                             ▼                     ▼
                    │ Orchestrator    │                    ┌─────────────────┐  ┌──────────────────┐
                    │ (Airflow DAGs:  │                    │ Semantic Metrics │  │ React UI          │
                    │  batch + NRT)   │                    │  layer (dbt      │  │  - Report builder │
                    └─────────────────┘                    │  metrics + YAML) │  │  - Dashboards     │
                                                           └─────────────────┘  └──────────────────┘
```

Two planes:

- **Control plane** — multi-tenant metadata: tenants, users/roles, connector configs, secrets,
  field mappings, metric definitions, dashboard layouts. Source of truth for *how* a tenant's data is
  ingested and modeled. Stored in Postgres (`control` schema) + a secrets vault (KMS-backed).
- **Data plane** — actual tenant business data flowing Source → Bronze → Silver(canonical) → Gold(marts).

### Medallion layering
| Layer | Schema | Content | Owner |
|-------|--------|---------|-------|
| Bronze | `raw_<tenant>` | Source-shaped, append-only, with `_ingested_at`, `_batch_id` | Connectors |
| Silver | `canonical_<tenant>` | Canonical entities (Customers, Orders, …) after mapping + validation | Mapping engine |
| Gold | `marts_<tenant>` | Star-schema facts/dims + metrics for BI | dbt |

---

## 2. Data Connectivity Layer

Connectors implement a single SDK interface (`backend/app/connectors/sdk.py`):

```python
class Connector(Protocol):
    def test_connection(self) -> ConnectionStatus: ...
    def discover(self) -> list[StreamSchema]: ...                 # available streams + schema
    def read(self, stream: str, state: SyncState) -> Iterator[Record]: ...  # incremental
    def supports_cdc(self) -> bool: ...
```

- **REST** (`rest.py`): pagination strategies (cursor, page, offset, link-header), rate-limit aware,
  JSONPath record selection.
- **JDBC/ODBC** (`jdbc.py`): SQLAlchemy-backed; high-watermark incremental via a cursor column;
  CDC via change tables / `xmin` / `ora_rowscn` where the engine supports it.
- **FlatFile** (`flatfile.py`): CSV/Excel from local, S3, or SFTP; schema inference + explicit schema.
- **MCP adapter** (`mcp.py`): treats MCP servers as modular data adapters exposing tools as streams.

Cross-cutting concerns live in `connectors/runtime.py`:
- **Auth**: `OAuth2ClientCredentials`, `OAuth2AuthCode`, `ApiKeyAuth`, `BasicAuth`, `StaticTokenAuth`,
  all resolved from the **secrets vault** (`core/secrets.py`) — configs store *references*, never values.
- **Incremental + CDC**: `SyncState` (cursor field + value + per-stream watermarks) persisted per run.
- **Retry + fault tolerance**: `@resilient` decorator — exponential backoff with jitter, circuit
  breaker, and dead-letter for poison records.

### Connector config (declarative, per tenant)
```yaml
# config/tenants/acme-mfg/connectors/erp.yaml
id: epicor-prod
type: rest
auth:
  kind: oauth2_client_credentials
  token_url: https://erp.example.com/oauth/token
  client_id_ref: vault://acme-mfg/epicor/client_id      # resolved at runtime
  client_secret_ref: vault://acme-mfg/epicor/client_secret
streams:
  - name: SalesOrders
    path: /api/v2/SalesOrders
    primary_key: [OrderNum]
    cursor_field: ChangedDate
    pagination: { kind: page, size: 200 }
```

---

## 3. Data Modeling & Semantic Layer

### Canonical entities (`backend/app/canonical/`)
Core (all verticals): `Customer, Vendor, Product, InventoryLevel, Order, OrderLine, Invoice,
InvoiceLine, Payment, GLAccount, GLEntry, Job, WorkOrder`.

Industry extension packs (`canonical/extensions/`):
- **Manufacturing**: `BOM, BOMComponent, Routing, RoutingOperation, ProductionRun, JobCost`
- **Distribution**: inventory-turn / fill-rate fields on `InventoryLevel`, `OrderLine` fulfillment
- **Construction**: `Project, CostCode, Budget, BudgetLine, Schedule, ScheduleTask`
- **Field Service**: `ServiceTicket, Dispatch, Technician, SLA`
- **Finance**: `GLAccount` roll-ups, AR/AP aging derived in marts

Every canonical record carries lineage: `tenant_id, source_system, source_id, _ingested_at, _hash`.

### Warehouse model — **star schema** (`warehouse/sql/`)
Facts: `fact_sales`, `fact_invoice`, `fact_inventory_snapshot`, `fact_gl`, `fact_job_cost`,
`fact_production`, `fact_service_ticket`.
Conformed dims: `dim_date`, `dim_customer`, `dim_product`, `dim_vendor`, `dim_employee`,
`dim_job`, `dim_account`, `dim_location`. (Data-vault variant noted in `warehouse/sql/README.md`.)

### Semantic metrics layer (`warehouse/dbt/`)
dbt models build the marts; metrics are declared in `warehouse/dbt/metrics/*.yml` (dbt Semantic Layer
style) so a metric like `gross_margin_pct` is defined once and reused by API, dashboards, and NLQ.

---

## 4. Data Pipeline Architecture

```
extract (connector, incremental/CDC)
   └▶ land to Bronze (raw_<tenant>)            [Airflow task: extract_<stream>]
        └▶ map → Canonical (validate)          [task: map_<entity>]   (Great-Expectations-style rules)
             └▶ dbt run (Silver→Gold marts)    [task: dbt_build]
                  └▶ dbt test + freshness       [task: dbt_test]
                       └▶ refresh metrics cache  [task: metrics_refresh]
                            └▶ insights scan      [task: insights_scan]
```

- **Batch + near-real-time**: batch DAG on schedule; NRT via short-interval micro-batches or
  source webhooks → queue → same map/transform path.
- **Validation**: declarative rules (`pipeline/validation.py`) — not-null, unique PK, referential,
  range, freshness; failures route to quarantine + alert, good rows proceed.
- **Freshness strategy**: each stream has an SLA (`max_lag`); freshness recorded per run and surfaced
  as a `data_freshness` metric and a badge in the UI.
- **Multi-tenant isolation**: schema-per-tenant in the warehouse (`marts_<tenant>`) with a shared
  control plane; large tenants can be promoted to a dedicated database/warehouse without code change.

See `orchestration/airflow/dags/elt_pipeline.py` for the example DAG.

---

## 5. Reporting & Dashboard Layer
- **Drag-and-drop report builder** (`frontend/src/builder/`): pick a dataset (a mart/metric set),
  drag dimensions/measures, choose viz, add filters → produces a **report spec JSON** persisted per
  tenant and executed by the metrics API.
- **Prebuilt industry templates** (`frontend/dashboards/*.json`): Manufacturing, Distribution,
  Construction, Executive.
- **Drill-down + filtering + cross-source joins**: handled at the semantic layer (conformed dims let
  facts from different sources join on the same keys).

Dashboard config is JSON (see `frontend/dashboards/manufacturing.json`) — fully declarative.

---

## 6. Insights & Intelligence Layer (`backend/app/insights/`)
Hybrid **rule-based + ML**, all outputs **explainable**.
- **Anomaly detection** (`anomaly.py`): robust z-score / STL residual + seasonal-aware thresholds on
  any metric time series (margin drop, inventory spike).
- **Forecasting** (`forecast.py`): Holt-Winters / simple exponential smoothing baseline; pluggable to
  Prophet/ML. Used for sales + demand.
- **Natural language queries** (`nlq.py`): NL → structured metric query against the semantic layer
  (LLM maps to whitelisted metrics/dims; deterministic execution; answer + the query it ran).
- **Prescriptive recommendations** (`recommendations.py`): rules over metrics + anomalies →
  actionable suggestions with the evidence that triggered them.

Every insight returns `{title, severity, explanation, evidence[], recommended_actions[]}`.

---

## 7. Configuration & Extensibility
- **Mapping layer** (`backend/app/mapping/`): YAML maps `source field → canonical field` with
  transforms (cast, lookup, expression, default, concat). Versioned per tenant + source.
- **Custom metrics builder**: metrics defined in YAML/JSON; tenants can add their own without deploys.
- **Plugin architecture**: verticals register via entry points (`industry_packs/`) contributing
  canonical extensions, dbt models, metrics, dashboards, and rules.
- **Multi-tenant config storage**: `control` schema + Git-backed `config/tenants/` for review/audit.

---

## 8. Tech stack
| Concern | Choice | Rationale |
|--------|--------|-----------|
| Connectors/API/Insights | **Python 3.12 + FastAPI** | Rich data/ML ecosystem, async API |
| Orchestration | **Airflow** | Mature DAGs, backfills, SLAs |
| Transform/semantic | **dbt** | Versioned SQL models + metrics layer |
| Warehouse | **Postgres** (dev) → **Snowflake/BigQuery** (scale) | Same dbt code, swap adapter |
| Frontend | **React + TypeScript + Vite** | Component-driven report builder |
| Auth | **OIDC multi-tenant** (Auth0/Cognito) + internal RBAC | SaaS-grade |
| Secrets | **KMS-backed vault** (AWS Secrets Manager / Vault) | No creds in config |
| Deploy | **Cloud-native (AWS): ECS/EKS, RDS, S3, Secrets Manager** | Standard, SOC2-friendly |

---

## 9. Security & multi-tenancy
- **Isolation**: `tenant_id` on every control-plane row + RLS; schema-per-tenant in the warehouse.
- **Secrets**: configs hold `vault://` references only; resolved at runtime, never logged.
- **RBAC**: roles (owner/admin/analyst/viewer) scoped to tenant; enforced in API dependency.
- **Audit**: append-only audit log for config changes, data access, and insight generation.
- **Compliance**: encryption at rest/in transit, least-privilege IAM, data-retention policies —
  SOC2-ready posture.

---

## 10. How the pieces connect (request → answer)
1. UI requests `gross_margin_pct by month for vertical=manufacturing`.
2. Metrics API resolves the metric from the semantic layer → compiles SQL against `marts_<tenant>`.
3. Result cached; returned to the dashboard/report.
4. Insights scan runs the same metric through anomaly + forecast and attaches explanations.
5. NLQ ("why did margins drop last month?") maps to the same metric path + a driver decomposition.
