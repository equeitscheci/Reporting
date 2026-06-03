"""Insights engine — scans governed metrics, attaches anomalies, forecasts, and recommendations.

Output is a list of `Insight` objects, each fully explainable: title, severity, the human-readable
explanation, the evidence rows that triggered it, and recommended actions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.insights.anomaly import AnomalyDetector
from app.insights.forecast import forecast_series
from app.insights.recommendations import recommend_for_anomaly
from app.metrics.definitions import METRICS, metrics_for_industry
from app.metrics.engine import MetricEngine, MetricQuery


@dataclass
class Insight:
    id: str
    kind: str  # anomaly|forecast|trend
    title: str
    severity: str  # info|warning|critical
    metric: str
    explanation: str
    evidence: list[dict[str, Any]] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__


# Direction of badness per metric: a "drop" in margin is bad; a "spike" in inventory is bad.
_BAD_DIRECTION = {
    "gross_margin_pct": "drop",
    "gross_margin": "drop",
    "revenue": "drop",
    "fill_rate": "drop",
    "order_count": "drop",
    "inventory_value": "spike",
    "qty_on_hand": "spike",
    "ar_open_balance": "spike",
    "job_margin_pct": "drop",
}


class InsightsEngine:
    def __init__(self, metric_engine: MetricEngine, threshold: float = 2.5) -> None:
        self.metrics = metric_engine
        self.detector = AnomalyDetector(threshold=threshold)

    def scan(
        self, tenant_id: str, industry: str | None = None, metrics: list[str] | None = None
    ) -> list[Insight]:
        names = metrics or [m.name for m in metrics_for_industry(industry)]
        insights: list[Insight] = []
        for name in names:
            mdef = METRICS.get(name)
            if mdef is None or "month" not in (mdef.default_dimensions or ["month"]):
                pass
            insights.extend(self._scan_metric(tenant_id, name))
        # Most severe first.
        order = {"critical": 0, "warning": 1, "info": 2}
        return sorted(insights, key=lambda i: order.get(i.severity, 3))

    def _scan_metric(self, tenant_id: str, name: str) -> list[Insight]:
        mdef = METRICS[name]
        result = self.metrics.query(
            tenant_id, MetricQuery(metric=name, dimensions=["month"], order_by=None)
        )
        series = [r for r in result.rows if r.get("month")]
        series.sort(key=lambda r: r["month"])
        labels = [r["month"] for r in series]
        values = [float(r["value"]) for r in series]
        if len(values) < 4:
            return []

        out: list[Insight] = []
        anomalies = self.detector.detect(labels, values)
        bad_dir = _BAD_DIRECTION.get(name)
        for a in anomalies:
            severity = "critical" if (bad_dir and a.direction == bad_dir) else "warning"
            actions = recommend_for_anomaly(name, a, tenant_id, self.metrics)
            out.append(
                Insight(
                    id=f"{name}:{a.label}:{a.direction}",
                    kind="anomaly",
                    title=f"{mdef.label} {a.direction} at {a.label}",
                    severity=severity,
                    metric=name,
                    explanation=a.explain(mdef.label, mdef.unit),
                    evidence=[{"month": labels[i], "value": values[i]} for i in range(len(labels))][-6:],
                    recommended_actions=actions,
                )
            )

        # Forward-looking forecast insight for primary metrics.
        if name in ("revenue", "gross_margin"):
            fc = forecast_series(labels, values, horizon=3)
            nxt = fc.points[0]
            direction = "up" if nxt.value >= values[-1] else "down"
            out.append(
                Insight(
                    id=f"{name}:forecast",
                    kind="forecast",
                    title=f"{mdef.label} forecast trending {direction}",
                    severity="info",
                    metric=name,
                    explanation=(
                        f"Next period ({nxt.label}) {mdef.label} projected at "
                        f"{nxt.value:,.0f} (range {nxt.lower:,.0f}–{nxt.upper:,.0f}) "
                        f"via {fc.method}."
                    ),
                    evidence=[p.__dict__ for p in fc.points],
                    recommended_actions=[],
                )
            )
        return out
