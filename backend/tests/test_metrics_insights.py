"""Metrics engine, insights (anomaly/forecast), NLQ, and report runner — end to end on the demo tenant."""

from __future__ import annotations

import pytest

from app.insights.anomaly import detect_anomalies
from app.insights.engine import InsightsEngine
from app.insights.forecast import forecast_series
from app.insights.nlq import NLQueryEngine
from app.metrics.engine import MetricQuery
from app.reports.runner import run_report_spec
from app.services import metric_engine, seed_tenant

TENANT = "acme-mfg"


@pytest.fixture(scope="module", autouse=True)
def seeded():
    seed_tenant(TENANT)


def test_revenue_metric_has_monthly_series():
    res = metric_engine.query(TENANT, MetricQuery(metric="revenue", dimensions=["month"]))
    assert res.unit == "currency"
    assert len(res.rows) >= 6
    assert all("value" in r for r in res.rows)


def test_gross_margin_pct_is_ratio():
    res = metric_engine.query(TENANT, MetricQuery(metric="gross_margin_pct", dimensions=["month"]))
    vals = [r["value"] for r in res.rows]
    assert all(0 <= v <= 100 for v in vals)


def test_anomaly_detection_flags_margin_drop():
    res = metric_engine.query(TENANT, MetricQuery(metric="gross_margin_pct", dimensions=["month"]))
    rows = sorted(res.rows, key=lambda r: r["month"])
    labels = [r["month"] for r in rows]
    values = [r["value"] for r in rows]
    anomalies = detect_anomalies(labels, values, threshold=2.5)
    assert any(a.direction == "drop" for a in anomalies)


def test_forecast_returns_horizon():
    fc = forecast_series(["2026-01", "2026-02", "2026-03", "2026-04"], [10, 12, 11, 13], horizon=3)
    assert len(fc.points) == 3
    assert fc.method == "holt_linear"


def test_insights_engine_produces_critical_margin_insight():
    insights = InsightsEngine(metric_engine).scan(TENANT, industry="manufacturing")
    assert any(i.metric == "gross_margin_pct" and i.severity == "critical" for i in insights)
    crit = next(i for i in insights if i.metric == "gross_margin_pct" and i.kind == "anomaly")
    assert crit.explanation
    assert crit.recommended_actions


def test_nlq_why_margins_dropped():
    nlq = NLQueryEngine(metric_engine)
    ans = nlq.answer(TENANT, "Why did margins drop last month?")
    assert ans.resolved.metric == "gross_margin_pct"
    assert ans.resolved.intent == "why"
    assert "contributors" in ans.answer.lower()


def test_nlq_lookup_revenue_by_region():
    nlq = NLQueryEngine(metric_engine)
    ans = nlq.answer(TENANT, "show revenue by region")
    assert ans.resolved.metric == "revenue"
    assert "region" in ans.resolved.dimensions


def test_report_runner_executes_spec():
    spec = {
        "title": "Test",
        "widgets": [
            {"id": "w1", "type": "line", "metric": "revenue", "dimensions": ["month"]},
            {"id": "w2", "type": "bar", "metric": "gross_margin_pct", "dimensions": ["product_group"]},
        ],
    }
    out = run_report_spec(TENANT, spec, metric_engine)
    assert len(out["widgets"]) == 2
    assert out["widgets"][0]["data"]
