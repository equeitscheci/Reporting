"""Prescriptive recommendations — rules over metrics + anomalies producing actionable advice.

Each recommendation is tied to the evidence that triggered it (the anomaly + a driver decomposition),
so users see *why* an action is suggested, not just *what*. This is the rule half of the hybrid;
Phase 2 layers learned ranking on top.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.metrics.engine import MetricQuery

if TYPE_CHECKING:
    from app.insights.anomaly import Anomaly
    from app.metrics.engine import MetricEngine


def recommend_for_anomaly(
    metric: str, anomaly: "Anomaly", tenant_id: str, engine: "MetricEngine"
) -> list[str]:
    """Return concrete next steps for a detected anomaly, enriched with top drivers."""

    if metric in ("gross_margin_pct", "gross_margin", "job_margin_pct") and anomaly.direction == "drop":
        drivers = _top_drivers(engine, tenant_id, "gross_margin", "product_group", anomaly.label)
        recs = [
            "Review discounting and price exceptions for the affected period.",
            "Check for supplier cost increases not yet reflected in list prices.",
        ]
        if drivers:
            recs.append(
                "Largest margin contributors to investigate: "
                + ", ".join(f"{d['product_group']} (${d['value']:,.0f})" for d in drivers)
            )
        return recs

    if metric in ("inventory_value", "qty_on_hand") and anomaly.direction == "spike":
        drivers = _top_drivers(
            engine, tenant_id, "inventory_value", "product_group", anomaly.label, fact="inventory"
        )
        recs = [
            "Flag slow-moving SKUs for markdown or return-to-vendor.",
            "Re-check reorder points/safety stock against recent demand.",
        ]
        if drivers:
            recs.append(
                "Inventory build concentrated in: "
                + ", ".join(f"{d['product_group']} (${d['value']:,.0f})" for d in drivers)
            )
        return recs

    if metric == "fill_rate" and anomaly.direction == "drop":
        return [
            "Investigate stock-outs and backorders for top-velocity SKUs.",
            "Review supplier lead-time adherence for the period.",
        ]

    if metric == "ar_open_balance" and anomaly.direction == "spike":
        return [
            "Prioritize collections on the largest past-due accounts.",
            "Review credit terms for customers with rising open balances.",
        ]

    if metric == "revenue" and anomaly.direction == "drop":
        return [
            "Segment the decline by customer and region to localize the cause.",
            "Check for churned or paused accounts versus pricing/volume effects.",
        ]
    return ["Investigate the drivers behind this change and confirm data completeness."]


def _top_drivers(
    engine: "MetricEngine",
    tenant_id: str,
    metric: str,
    dimension: str,
    period: str | None,
    fact: str = "sales",
    top_n: int = 3,
) -> list[dict]:
    try:
        filters = {"month": period} if period else {}
        res = engine.query(
            tenant_id,
            MetricQuery(metric=metric, dimensions=[dimension], filters=filters,
                        order_by="value", limit=top_n),
        )
        return [r for r in res.rows if r.get(dimension)]
    except Exception:  # noqa: BLE001
        return []


def generate_recommendations(tenant_id: str, engine: "MetricEngine", industry: str | None = None):
    """Convenience: scan + collect just the recommendations (used by the API)."""

    from app.insights.engine import InsightsEngine

    insights = InsightsEngine(engine).scan(tenant_id, industry=industry)
    return [
        {"metric": i.metric, "title": i.title, "severity": i.severity,
         "actions": i.recommended_actions}
        for i in insights
        if i.recommended_actions
    ]
