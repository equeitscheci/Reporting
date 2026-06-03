-- =====================================================================================
-- Silver layer: canonical (ERP-agnostic) entities, per-tenant schema.
-- The mapping engine writes here. Field names match the Pydantic canonical model exactly.
-- Multi-tenant isolation: one schema per tenant (e.g. canonical_acme_mfg). Large tenants can be
-- promoted to a dedicated database with no DDL changes.
-- Dialect: PostgreSQL (also valid with minor type tweaks on Snowflake/BigQuery via dbt).
-- =====================================================================================

CREATE SCHEMA IF NOT EXISTS canonical_acme_mfg;
SET search_path TO canonical_acme_mfg;

-- Lineage columns appear on every table: tenant_id, source_system, source_id, ingested_at, row_hash.

CREATE TABLE IF NOT EXISTS customer (
    tenant_id      TEXT NOT NULL,
    source_system  TEXT NOT NULL,
    source_id      TEXT NOT NULL,
    name           TEXT NOT NULL,
    region         TEXT,
    segment        TEXT,
    status         TEXT,
    credit_limit   NUMERIC(18,2),
    ingested_at    TIMESTAMPTZ DEFAULT now(),
    row_hash       TEXT,
    PRIMARY KEY (tenant_id, source_system, source_id)
);

CREATE TABLE IF NOT EXISTS vendor (
    tenant_id      TEXT NOT NULL,
    source_system  TEXT NOT NULL,
    source_id      TEXT NOT NULL,
    name           TEXT NOT NULL,
    region         TEXT,
    status         TEXT,
    ingested_at    TIMESTAMPTZ DEFAULT now(),
    row_hash       TEXT,
    PRIMARY KEY (tenant_id, source_system, source_id)
);

CREATE TABLE IF NOT EXISTS product (
    tenant_id      TEXT NOT NULL,
    source_system  TEXT NOT NULL,
    source_id      TEXT NOT NULL,
    sku            TEXT NOT NULL,
    description    TEXT,
    product_group  TEXT,
    standard_cost  NUMERIC(18,4),
    list_price     NUMERIC(18,4),
    uom            TEXT,
    ingested_at    TIMESTAMPTZ DEFAULT now(),
    row_hash       TEXT,
    PRIMARY KEY (tenant_id, source_system, source_id)
);

CREATE TABLE IF NOT EXISTS inventory_level (
    tenant_id      TEXT NOT NULL,
    source_system  TEXT NOT NULL,
    source_id      TEXT NOT NULL,
    sku            TEXT NOT NULL,
    location       TEXT,
    snapshot_date  DATE NOT NULL,
    qty_on_hand    NUMERIC(18,4) DEFAULT 0,
    unit_cost      NUMERIC(18,4),
    qty_committed  NUMERIC(18,4),
    qty_on_order   NUMERIC(18,4),
    ingested_at    TIMESTAMPTZ DEFAULT now(),
    row_hash       TEXT,
    PRIMARY KEY (tenant_id, source_system, source_id)
);

CREATE TABLE IF NOT EXISTS "order" (
    tenant_id      TEXT NOT NULL,
    source_system  TEXT NOT NULL,
    source_id      TEXT NOT NULL,
    order_number   TEXT NOT NULL,
    customer_id    TEXT NOT NULL,
    order_date     DATE,
    status         TEXT,
    currency       TEXT DEFAULT 'USD',
    ingested_at    TIMESTAMPTZ DEFAULT now(),
    row_hash       TEXT,
    PRIMARY KEY (tenant_id, source_system, source_id)
);

CREATE TABLE IF NOT EXISTS order_line (
    tenant_id      TEXT NOT NULL,
    source_system  TEXT NOT NULL,
    source_id      TEXT NOT NULL,
    order_number   TEXT NOT NULL,
    line_number    INTEGER NOT NULL,
    sku            TEXT NOT NULL,
    order_qty      NUMERIC(18,4) DEFAULT 0,
    ship_qty       NUMERIC(18,4),
    unit_price     NUMERIC(18,4) DEFAULT 0,
    unit_cost      NUMERIC(18,4) DEFAULT 0,
    ingested_at    TIMESTAMPTZ DEFAULT now(),
    row_hash       TEXT,
    PRIMARY KEY (tenant_id, source_system, source_id)
);

CREATE TABLE IF NOT EXISTS invoice (
    tenant_id      TEXT NOT NULL,
    source_system  TEXT NOT NULL,
    source_id      TEXT NOT NULL,
    invoice_number TEXT NOT NULL,
    order_number   TEXT,
    customer_id    TEXT NOT NULL,
    invoice_date   DATE,
    due_date       DATE,
    amount         NUMERIC(18,2) DEFAULT 0,
    amount_paid    NUMERIC(18,2) DEFAULT 0,
    ingested_at    TIMESTAMPTZ DEFAULT now(),
    row_hash       TEXT,
    PRIMARY KEY (tenant_id, source_system, source_id)
);

CREATE TABLE IF NOT EXISTS gl_entry (
    tenant_id      TEXT NOT NULL,
    source_system  TEXT NOT NULL,
    source_id      TEXT NOT NULL,
    entry_id       TEXT NOT NULL,
    account_code   TEXT NOT NULL,
    posting_date   DATE,
    debit          NUMERIC(18,2) DEFAULT 0,
    credit         NUMERIC(18,2) DEFAULT 0,
    job_id         TEXT,
    memo           TEXT,
    ingested_at    TIMESTAMPTZ DEFAULT now(),
    row_hash       TEXT,
    PRIMARY KEY (tenant_id, source_system, source_id)
);

-- Manufacturing extension (created only when the tenant enables the pack).
CREATE TABLE IF NOT EXISTS job_cost (
    tenant_id      TEXT NOT NULL,
    source_system  TEXT NOT NULL,
    source_id      TEXT NOT NULL,
    job_number     TEXT NOT NULL,
    cost_code      TEXT,
    cost_type      TEXT,          -- material|labor|burden|subcontract
    amount         NUMERIC(18,2) DEFAULT 0,
    posting_date   DATE,
    ingested_at    TIMESTAMPTZ DEFAULT now(),
    row_hash       TEXT,
    PRIMARY KEY (tenant_id, source_system, source_id)
);

CREATE INDEX IF NOT EXISTS ix_order_line_order ON order_line (order_number);
CREATE INDEX IF NOT EXISTS ix_order_customer ON "order" (customer_id);
CREATE INDEX IF NOT EXISTS ix_invoice_customer ON invoice (customer_id);
CREATE INDEX IF NOT EXISTS ix_inventory_snapshot ON inventory_level (snapshot_date);
