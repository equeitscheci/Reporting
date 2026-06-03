"""Execute a declarative report/dashboard spec against the metrics engine.

A report spec (the same JSON the drag-and-drop builder emits and dashboards store) is a list of
widgets, each referencing a metric + dimensions + filters. The runner resolves every widget through
the governed semantic layer, so the builder, saved reports, and prebuilt dashboards all share one
execution path.

Spec shape:
{
  "title": "...",
  "filters": { "month": ["2026-04"] },          # dashboard-level filters merged into each widget
  "widgets": [
    {"id": "w1", "type": "line", "metric": "revenue", "dimensions": ["month"]},
    {"id": "w2", "type": "bar",  "metric": "gross_margin_pct", "dimensions": ["product_group"],
     "filters": {"region": "West"}, "limit": 10}
  ]
}
"""

from __future__ import annotations

from typing import Any

from app.metrics.engine import MetricEngine, MetricQuery


def run_report_spec(
    tenant_id: str, spec: dict[str, Any], engine: MetricEngine
) -> dict[str, Any]:
    dashboard_filters = spec.get("filters", {})
    results: list[dict[str, Any]] = []

    for widget in spec.get("widgets", []):
        metric = widget.get("metric")
        if not metric:
            results.append({"id": widget.get("id"), "error": "widget missing 'metric'"})
            continue
        filters = {**dashboard_filters, **widget.get("filters", {})}
        try:
            res = engine.query(
                tenant_id,
                MetricQuery(
                    metric=metric,
                    dimensions=widget.get("dimensions", []),
                    filters=filters,
                    order_by=widget.get("order_by"),
                    limit=widget.get("limit"),
                ),
            )
            results.append(
                {
                    "id": widget.get("id"),
                    "type": widget.get("type", "table"),
                    "title": widget.get("title", res.label),
                    "metric": metric,
                    "unit": res.unit,
                    "dimensions": res.dimensions,
                    "data": res.rows,
                }
            )
        except Exception as exc:  # noqa: BLE001
            results.append({"id": widget.get("id"), "metric": metric, "error": str(exc)})

    return {"title": spec.get("title", "Report"), "widgets": results}
