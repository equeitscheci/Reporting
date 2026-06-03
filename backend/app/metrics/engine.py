"""Metric query engine — computes a metric (optionally sliced/filtered) over the star-schema facts.

The same engine powers ad-hoc reports, dashboards, NLQ, and the insights time-series scans, so a
metric is computed identically no matter who asks. In production this compiles to SQL against
`marts_<tenant>`; here it executes equivalent pandas group-bys over the in-memory facts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from app.metrics.definitions import METRICS, MetricDef
from app.metrics.facts import FACT_BUILDERS
from app.store.memory import CanonicalStore


@dataclass
class MetricQuery:
    metric: str
    dimensions: list[str] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)
    time_grain: str | None = None  # None uses the metric's stored 'month' column as-is
    order_by: str | None = None
    limit: int | None = None


@dataclass
class MetricResult:
    metric: str
    label: str
    unit: str
    dimensions: list[str]
    rows: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "label": self.label,
            "unit": self.unit,
            "dimensions": self.dimensions,
            "rows": self.rows,
        }


class MetricEngine:
    def __init__(self, store: CanonicalStore) -> None:
        self.store = store
        self._fact_cache: dict[tuple[str, str], pd.DataFrame] = {}

    def fact(self, tenant_id: str, fact_name: str) -> pd.DataFrame:
        key = (tenant_id, fact_name)
        if key not in self._fact_cache:
            self._fact_cache[key] = FACT_BUILDERS[fact_name](self.store, tenant_id)
        return self._fact_cache[key]

    def invalidate(self, tenant_id: str) -> None:
        self._fact_cache = {k: v for k, v in self._fact_cache.items() if k[0] != tenant_id}

    def query(self, tenant_id: str, q: MetricQuery) -> MetricResult:
        mdef = METRICS.get(q.metric)
        if mdef is None:
            raise KeyError(f"Unknown metric '{q.metric}'. Known: {sorted(METRICS)}")
        df = self.fact(tenant_id, mdef.fact)
        dims = q.dimensions or mdef.default_dimensions

        if df.empty:
            return MetricResult(mdef.name, mdef.label, mdef.unit, dims, [])

        df = self._apply_filters(df, q.filters)
        rows = self._aggregate(df, mdef, dims)

        if q.order_by:
            rows = sorted(rows, key=lambda r: r.get(q.order_by, 0), reverse=True)
        elif dims:
            rows = sorted(rows, key=lambda r: tuple(str(r.get(d, "")) for d in dims))
        if q.limit:
            rows = rows[: q.limit]
        return MetricResult(mdef.name, mdef.label, mdef.unit, dims, rows)

    # ------------------------------------------------------------------ internals
    def _apply_filters(self, df: pd.DataFrame, filters: dict[str, Any]) -> pd.DataFrame:
        for col, val in filters.items():
            if col not in df.columns:
                continue
            if isinstance(val, (list, tuple)):
                df = df[df[col].isin(val)]
            else:
                df = df[df[col] == val]
        return df

    def _aggregate(
        self, df: pd.DataFrame, mdef: MetricDef, dims: list[str]
    ) -> list[dict[str, Any]]:
        dims = [d for d in dims if d in df.columns]

        def agg_value(frame: pd.DataFrame) -> float:
            if mdef.agg == "ratio":
                num = self._measure(frame, mdef.numerator)
                den = self._measure(frame, mdef.denominator)
                pct = (num / den) if den else 0.0
                return round(pct * (100 if mdef.unit == "percent" else 1), 4)
            if mdef.agg == "count_distinct":
                return int(frame[mdef.measure].nunique())
            if mdef.agg == "count":
                return int(len(frame))
            series = pd.to_numeric(frame[mdef.measure], errors="coerce")
            val = getattr(series, {"sum": "sum", "avg": "mean", "min": "min", "max": "max"}[mdef.agg])()
            return round(float(val), 4)

        if not dims:
            return [{"value": agg_value(df)}]

        out: list[dict[str, Any]] = []
        for keys, group in df.groupby(dims, dropna=False):
            keys = keys if isinstance(keys, tuple) else (keys,)
            row = {d: (None if pd.isna(k) else k) for d, k in zip(dims, keys)}
            row["value"] = agg_value(group)
            out.append(row)
        return out

    def _measure(self, frame: pd.DataFrame, measure: str | None) -> float:
        if measure is None:
            return 0.0
        if measure.endswith("_distinct"):
            base = measure[: -len("_distinct")]
            return float(frame[base].nunique()) if base in frame.columns else 0.0
        if measure not in frame.columns:
            return 0.0
        return float(pd.to_numeric(frame[measure], errors="coerce").sum())
