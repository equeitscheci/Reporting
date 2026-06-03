"""Natural-language queries → governed metric queries.

Phase 1 is a deterministic resolver: it maps a question to a *whitelisted* metric + dimensions + time
filter from the semantic layer, executes it, and returns the answer together with the exact query it
ran (explainability + safety — the model can never run arbitrary SQL). "Why" questions trigger a
driver decomposition. Phase 2 swaps the keyword matcher for an LLM that emits the same structured
MetricQuery, so execution stays deterministic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.metrics.definitions import METRICS
from app.metrics.engine import MetricEngine, MetricQuery

# Synonyms mapping common phrasing → metric name.
_METRIC_SYNONYMS = {
    "margin": "gross_margin_pct",
    "margins": "gross_margin_pct",
    "gross margin": "gross_margin_pct",
    "profit": "gross_margin",
    "revenue": "revenue",
    "sales": "revenue",
    "cogs": "cogs",
    "cost of goods": "cogs",
    "orders": "order_count",
    "order count": "order_count",
    "fill rate": "fill_rate",
    "inventory": "inventory_value",
    "stock": "qty_on_hand",
    "ar": "ar_open_balance",
    "receivable": "ar_open_balance",
    "average order": "avg_order_value",
}

_DIMENSION_SYNONYMS = {
    "customer": "customer_name",
    "by customer": "customer_name",
    "region": "region",
    "by region": "region",
    "product": "product_group",
    "product group": "product_group",
    "category": "product_group",
    "segment": "segment",
    "month": "month",
    "over time": "month",
    "trend": "month",
}


@dataclass
class NLQuery:
    question: str
    metric: str
    dimensions: list[str] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)
    intent: str = "lookup"  # lookup|why|trend

    def to_metric_query(self) -> MetricQuery:
        return MetricQuery(metric=self.metric, dimensions=self.dimensions, filters=self.filters)


@dataclass
class NLAnswer:
    question: str
    resolved: NLQuery
    answer: str
    data: list[dict[str, Any]]
    explanation: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "resolved_query": {
                "metric": self.resolved.metric,
                "dimensions": self.resolved.dimensions,
                "filters": self.resolved.filters,
                "intent": self.resolved.intent,
            },
            "answer": self.answer,
            "data": self.data,
            "explanation": self.explanation,
        }


class NLQueryEngine:
    def __init__(self, engine: MetricEngine) -> None:
        self.engine = engine

    def parse(self, question: str, months: list[str] | None = None) -> NLQuery:
        q = question.lower()
        metric = self._match_metric(q)
        dims = self._match_dimensions(q)
        filters = self._match_time(q, months)
        intent = "why" if q.strip().startswith("why") or "why" in q else (
            "trend" if any(k in q for k in ("trend", "over time", "by month")) else "lookup"
        )
        if intent == "trend" and "month" not in dims:
            dims.append("month")
        return NLQuery(question=question, metric=metric, dimensions=dims, filters=filters,
                       intent=intent)

    def answer(self, tenant_id: str, question: str) -> NLAnswer:
        months = self._available_months(tenant_id)
        nlq = self.parse(question, months)
        mdef = METRICS[nlq.metric]

        if nlq.intent == "why":
            return self._answer_why(tenant_id, nlq, months)

        res = self.engine.query(tenant_id, nlq.to_metric_query())
        if not nlq.dimensions:
            val = res.rows[0]["value"] if res.rows else 0
            ans = f"{mdef.label} is {_fmt(val, mdef.unit)}" + (
                f" for {nlq.filters['month']}" if "month" in nlq.filters else ""
            )
        else:
            top = res.rows[: 5]
            ans = f"{mdef.label} by {', '.join(nlq.dimensions)}: " + "; ".join(
                f"{_label_of(r, nlq.dimensions)}={_fmt(r['value'], mdef.unit)}" for r in top
            )
        return NLAnswer(
            question=question,
            resolved=nlq,
            answer=ans,
            data=res.rows,
            explanation=(
                f"Ran metric '{nlq.metric}' grouped by {nlq.dimensions or 'none'} "
                f"with filters {nlq.filters or 'none'} against the semantic layer."
            ),
        )

    # ------------------------------------------------------------------ why / drivers
    def _answer_why(self, tenant_id: str, nlq: NLQuery, months: list[str]) -> NLAnswer:
        mdef = METRICS[nlq.metric]
        period = nlq.filters.get("month") or (months[-1] if months else None)
        prev = months[months.index(period) - 1] if period in months and months.index(period) > 0 else None

        cur = self._value(tenant_id, nlq.metric, {"month": period})
        prior = self._value(tenant_id, nlq.metric, {"month": prev}) if prev else None
        delta = (cur - prior) if prior is not None else None

        # Driver decomposition by product group.
        drivers = self.engine.query(
            tenant_id,
            MetricQuery(metric=nlq.metric if mdef.agg != "ratio" else "gross_margin",
                        dimensions=["product_group"], filters={"month": period},
                        order_by="value", limit=5),
        )
        driver_txt = ", ".join(
            f"{r.get('product_group')}={_fmt(r['value'], drivers.unit)}"
            for r in drivers.rows if r.get("product_group")
        )
        change = (
            f" changed by {_fmt(delta, mdef.unit)} vs {prev}" if delta is not None else ""
        )
        ans = (
            f"{mdef.label} for {period} was {_fmt(cur, mdef.unit)}{change}. "
            f"Largest contributors: {driver_txt or 'n/a'}."
        )
        return NLAnswer(
            question=nlq.question,
            resolved=nlq,
            answer=ans,
            data=drivers.rows,
            explanation=(
                f"Decomposed '{nlq.metric}' for {period} by product_group and compared to {prev} "
                "to identify drivers."
            ),
        )

    # ------------------------------------------------------------------ matching helpers
    def _match_metric(self, q: str) -> str:
        for phrase, name in sorted(_METRIC_SYNONYMS.items(), key=lambda x: -len(x[0])):
            if phrase in q:
                return name
        return "revenue"  # sensible default

    def _match_dimensions(self, q: str) -> list[str]:
        dims: list[str] = []
        for phrase, dim in _DIMENSION_SYNONYMS.items():
            if phrase in q and dim not in dims:
                dims.append(dim)
        return dims

    def _match_time(self, q: str, months: list[str] | None) -> dict[str, Any]:
        if not months:
            return {}
        m = re.search(r"(\d{4})-(\d{2})", q)
        if m:
            return {"month": m.group(0)}
        if "last month" in q or "previous month" in q:
            return {"month": months[-1]}
        if "this month" in q or "current month" in q:
            return {"month": months[-1]}
        return {}

    def _available_months(self, tenant_id: str) -> list[str]:
        res = self.engine.query(tenant_id, MetricQuery(metric="revenue", dimensions=["month"]))
        return sorted({r["month"] for r in res.rows if r.get("month")})

    def _value(self, tenant_id: str, metric: str, filters: dict) -> float:
        res = self.engine.query(tenant_id, MetricQuery(metric=metric, dimensions=[], filters=filters))
        return float(res.rows[0]["value"]) if res.rows else 0.0


def _fmt(v: Any, unit: str) -> str:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    if unit == "currency":
        return f"${v:,.0f}"
    if unit == "percent":
        return f"{v:.1f}%"
    return f"{v:,.1f}"


def _label_of(row: dict, dims: list[str]) -> str:
    return "/".join(str(row.get(d)) for d in dims)
