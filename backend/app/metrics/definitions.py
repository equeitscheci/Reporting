"""Governed metric definitions (semantic layer).

Each metric declares the fact it reads, how it aggregates, and (for ratios) numerator/denominator.
This Python registry is kept in lock-step with `warehouse/dbt/metrics/*.yml`; in production the dbt
Semantic Layer is the source of truth and this module is generated from it.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MetricDef:
    name: str
    label: str
    fact: str
    description: str = ""
    # Simple aggregation: agg over `measure`. Ratio: numerator/denominator measures.
    agg: str = "sum"  # sum|avg|count|count_distinct|ratio|min|max
    measure: str | None = None
    numerator: str | None = None
    denominator: str | None = None
    unit: str = "number"  # number|currency|percent|days|ratio
    default_dimensions: list[str] = field(default_factory=list)
    industry: str | None = None  # None = applies to all verticals

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "fact": self.fact,
            "unit": self.unit,
            "agg": self.agg,
            "industry": self.industry,
        }


_RAW: list[MetricDef] = [
    # ---------------------------------------------------------------- core / finance
    MetricDef("revenue", "Revenue", "fact_sales", "Total booked revenue", "sum", "revenue",
              unit="currency", default_dimensions=["month"]),
    MetricDef("cogs", "COGS", "fact_sales", "Cost of goods sold", "sum", "cost", unit="currency"),
    MetricDef("gross_margin", "Gross Margin $", "fact_sales", "Revenue minus COGS", "sum",
              "gross_margin", unit="currency", default_dimensions=["month"]),
    MetricDef("gross_margin_pct", "Gross Margin %", "fact_sales",
              "Gross margin as a percent of revenue", "ratio",
              numerator="gross_margin", denominator="revenue", unit="percent",
              default_dimensions=["month"]),
    MetricDef("order_count", "Orders", "fact_sales", "Distinct orders", "count_distinct",
              "order_number", unit="number"),
    MetricDef("avg_order_value", "Avg Order Value", "fact_sales", "Revenue per order", "ratio",
              numerator="revenue", denominator="order_number_distinct", unit="currency"),
    MetricDef("ar_open_balance", "AR Open Balance", "fact_invoice", "Unpaid invoice balance",
              "sum", "open_balance", unit="currency"),
    MetricDef("invoiced_amount", "Invoiced", "fact_invoice", "Total invoiced", "sum", "amount",
              unit="currency"),
    # ---------------------------------------------------------------- distribution
    MetricDef("fill_rate", "Fill Rate %", "fact_sales",
              "Shipped qty / ordered qty", "ratio", numerator="ship_qty",
              denominator="order_qty", unit="percent", industry="distribution"),
    MetricDef("inventory_value", "Inventory Value", "fact_inventory_snapshot",
              "On-hand value at cost", "sum", "inventory_value", unit="currency",
              industry="distribution"),
    MetricDef("qty_on_hand", "Qty On Hand", "fact_inventory_snapshot", "Units on hand", "sum",
              "qty_on_hand", unit="number", industry="distribution"),
    # ---------------------------------------------------------------- manufacturing
    MetricDef("job_margin_pct", "Job Margin %", "fact_sales",
              "Gross margin % (proxy for job profitability in demo)", "ratio",
              numerator="gross_margin", denominator="revenue", unit="percent",
              industry="manufacturing", default_dimensions=["customer_name"]),
]

METRICS: dict[str, MetricDef] = {m.name: m for m in _RAW}


def metrics_for_industry(industry: str | None) -> list[MetricDef]:
    return [m for m in METRICS.values() if m.industry in (None, industry)]
