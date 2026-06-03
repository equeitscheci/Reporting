"""Build star-schema fact tables (DataFrames) from canonical entities in the store.

These mirror the SQL marts in `warehouse/sql/` and dbt models: `fact_sales`, `fact_invoice`,
`fact_inventory_snapshot`. Conformed dimensions (customer, product) are joined in so metrics can
slice by any shared attribute and facts from different sources can be combined.
"""

from __future__ import annotations

import pandas as pd

from app.store.memory import CanonicalStore


def _empty(cols: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=cols)


def build_fact_sales(store: CanonicalStore, tenant_id: str) -> pd.DataFrame:
    lines = store.frame(tenant_id, "order_line")
    orders = store.frame(tenant_id, "order")
    customers = store.frame(tenant_id, "customer")
    products = store.frame(tenant_id, "product")
    if lines.empty or orders.empty:
        return _empty(
            ["order_number", "order_date", "month", "customer_id", "customer_name", "segment",
             "region", "sku", "product_group", "revenue", "cost", "gross_margin", "order_qty",
             "ship_qty"]
        )

    lines = lines.copy()
    lines["revenue"] = lines["order_qty"] * lines["unit_price"]
    lines["cost"] = lines["order_qty"] * lines["unit_cost"]
    lines["gross_margin"] = lines["revenue"] - lines["cost"]

    df = lines.merge(
        orders[["order_number", "order_date", "customer_id", "status"]],
        on="order_number",
        how="left",
    )
    if not customers.empty:
        cust = customers.rename(
            columns={"source_id": "customer_id", "name": "customer_name"}
        )[["customer_id", "customer_name", "segment", "region"]]
        df = df.merge(cust, on="customer_id", how="left")
    else:
        df["customer_name"] = None
        df["segment"] = None
        df["region"] = None
    if not products.empty:
        prod = products.rename(columns={"sku": "sku"})[["sku", "product_group"]]
        df = df.merge(prod, on="sku", how="left")
    else:
        df["product_group"] = None

    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    df["month"] = df["order_date"].dt.to_period("M").astype(str)
    return df


def build_fact_invoice(store: CanonicalStore, tenant_id: str) -> pd.DataFrame:
    inv = store.frame(tenant_id, "invoice")
    if inv.empty:
        return _empty(
            ["invoice_number", "customer_id", "invoice_date", "due_date", "month", "amount",
             "amount_paid", "open_balance"]
        )
    inv = inv.copy()
    inv["amount"] = pd.to_numeric(inv["amount"], errors="coerce").fillna(0.0)
    inv["amount_paid"] = pd.to_numeric(inv["amount_paid"], errors="coerce").fillna(0.0)
    inv["open_balance"] = inv["amount"] - inv["amount_paid"]
    inv["invoice_date"] = pd.to_datetime(inv["invoice_date"], errors="coerce")
    inv["due_date"] = pd.to_datetime(inv["due_date"], errors="coerce")
    inv["month"] = inv["invoice_date"].dt.to_period("M").astype(str)
    return inv


def build_fact_inventory(store: CanonicalStore, tenant_id: str) -> pd.DataFrame:
    snap = store.frame(tenant_id, "inventory_level")
    if snap.empty:
        return _empty(
            ["sku", "location", "snapshot_date", "month", "qty_on_hand", "unit_cost",
             "inventory_value", "product_group"]
        )
    snap = snap.copy()
    snap["qty_on_hand"] = pd.to_numeric(snap["qty_on_hand"], errors="coerce").fillna(0.0)
    snap["unit_cost"] = pd.to_numeric(snap["unit_cost"], errors="coerce").fillna(0.0)
    snap["inventory_value"] = snap["qty_on_hand"] * snap["unit_cost"]
    snap["snapshot_date"] = pd.to_datetime(snap["snapshot_date"], errors="coerce")
    snap["month"] = snap["snapshot_date"].dt.to_period("M").astype(str)
    products = store.frame(tenant_id, "product")
    if not products.empty:
        snap = snap.merge(products[["sku", "product_group"]], on="sku", how="left")
    else:
        snap["product_group"] = None
    return snap


FACT_BUILDERS = {
    "fact_sales": build_fact_sales,
    "fact_invoice": build_fact_invoice,
    "fact_inventory_snapshot": build_fact_inventory,
}
