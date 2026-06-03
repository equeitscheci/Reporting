# Warehouse SQL

Target-shape DDL for the medallion warehouse. In production, dbt builds Silver → Gold; these files
document the canonical (silver) tables and the star-schema marts (gold) and can be run directly on
Postgres for a from-scratch bootstrap.

| File | Layer | Contents |
|------|-------|----------|
| `01_canonical_silver.sql` | Silver | Canonical ERP-agnostic tables (per-tenant schema) |
| `02_marts_star_schema.sql` | Gold | Conformed dims + facts (`fact_sales`, `fact_invoice`, `fact_inventory_snapshot`, `fact_job_cost`) |

## Star schema vs Data Vault
This MVP ships a **Kimball star schema** because SMB BI workloads are read-heavy, dashboard-driven,
and benefit from simple, fast joins on conformed dimensions.

A **Data Vault** variant is appropriate at Phase 3 scale (thousands of tenants, many sources, heavy
auditability/lineage requirements). The mapping would be:

- **Hubs**: `hub_customer`, `hub_product`, `hub_order` (business keys + `tenant_id`).
- **Links**: `link_order_line` (order ↔ product), `link_invoice_order`.
- **Satellites**: `sat_customer_details`, `sat_product_pricing`, `sat_order_status` (descriptive,
  effectivity-dated attributes; the canonical `row_hash` becomes the satellite change driver).

The Gold marts (star schema above) are then built *from* the vault, so dashboards/metrics are
unchanged regardless of which modeling style underpins Silver.

## Multi-tenant isolation
Schema-per-tenant (`canonical_<tenant>` / `marts_<tenant>`). The control plane (tenant registry,
configs, secrets, RBAC) lives in a shared `control` schema with row-level security on `tenant_id`.
Promotion path: a large tenant can be moved to a dedicated database with no model changes.
