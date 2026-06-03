-- =====================================================================================
-- Gold layer: star-schema marts for BI. Conformed dimensions let facts from different sources
-- (and different ERPs) join on the same keys, enabling cross-source joins and drill-down.
-- Built by dbt in production (see warehouse/dbt/); this DDL documents the target shape.
-- =====================================================================================

CREATE SCHEMA IF NOT EXISTS marts_acme_mfg;
SET search_path TO marts_acme_mfg, canonical_acme_mfg;

-- ----------------------------------------------------------------- conformed dimensions
CREATE TABLE IF NOT EXISTS dim_date (
    date_key      INTEGER PRIMARY KEY,   -- yyyymmdd
    date          DATE NOT NULL,
    year          INTEGER,
    quarter       INTEGER,
    month         INTEGER,
    month_name    TEXT,
    week          INTEGER,
    day_of_week   INTEGER,
    is_weekend    BOOLEAN
);

CREATE TABLE IF NOT EXISTS dim_customer (
    customer_key  BIGSERIAL PRIMARY KEY,
    tenant_id     TEXT NOT NULL,
    customer_id   TEXT NOT NULL,
    customer_name TEXT,
    region        TEXT,
    segment       TEXT,
    UNIQUE (tenant_id, customer_id)
);

CREATE TABLE IF NOT EXISTS dim_product (
    product_key   BIGSERIAL PRIMARY KEY,
    tenant_id     TEXT NOT NULL,
    sku           TEXT NOT NULL,
    description   TEXT,
    product_group TEXT,
    standard_cost NUMERIC(18,4),
    list_price    NUMERIC(18,4),
    UNIQUE (tenant_id, sku)
);

-- ----------------------------------------------------------------- facts
-- Grain: one row per order line.
CREATE TABLE IF NOT EXISTS fact_sales (
    sales_key      BIGSERIAL PRIMARY KEY,
    tenant_id      TEXT NOT NULL,
    order_number   TEXT NOT NULL,
    line_number    INTEGER,
    date_key       INTEGER REFERENCES dim_date(date_key),
    customer_key   BIGINT REFERENCES dim_customer(customer_key),
    product_key    BIGINT REFERENCES dim_product(product_key),
    order_qty      NUMERIC(18,4),
    ship_qty       NUMERIC(18,4),
    revenue        NUMERIC(18,2),
    cost           NUMERIC(18,2),
    gross_margin   NUMERIC(18,2)
);

-- Grain: one row per invoice.
CREATE TABLE IF NOT EXISTS fact_invoice (
    invoice_key    BIGSERIAL PRIMARY KEY,
    tenant_id      TEXT NOT NULL,
    invoice_number TEXT NOT NULL,
    date_key       INTEGER REFERENCES dim_date(date_key),
    customer_key   BIGINT REFERENCES dim_customer(customer_key),
    amount         NUMERIC(18,2),
    amount_paid    NUMERIC(18,2),
    open_balance   NUMERIC(18,2),
    days_to_due    INTEGER
);

-- Grain: one row per (sku, location, snapshot_date).
CREATE TABLE IF NOT EXISTS fact_inventory_snapshot (
    inventory_key   BIGSERIAL PRIMARY KEY,
    tenant_id       TEXT NOT NULL,
    date_key        INTEGER REFERENCES dim_date(date_key),
    product_key     BIGINT REFERENCES dim_product(product_key),
    location        TEXT,
    qty_on_hand     NUMERIC(18,4),
    unit_cost       NUMERIC(18,4),
    inventory_value NUMERIC(18,2)
);

-- Grain: one row per job/cost-code/cost-type posting (manufacturing job costing).
CREATE TABLE IF NOT EXISTS fact_job_cost (
    job_cost_key  BIGSERIAL PRIMARY KEY,
    tenant_id     TEXT NOT NULL,
    job_number    TEXT NOT NULL,
    date_key      INTEGER REFERENCES dim_date(date_key),
    cost_code     TEXT,
    cost_type     TEXT,
    amount        NUMERIC(18,2)
);

CREATE INDEX IF NOT EXISTS ix_fact_sales_date ON fact_sales (date_key);
CREATE INDEX IF NOT EXISTS ix_fact_sales_cust ON fact_sales (customer_key);
CREATE INDEX IF NOT EXISTS ix_fact_sales_prod ON fact_sales (product_key);
