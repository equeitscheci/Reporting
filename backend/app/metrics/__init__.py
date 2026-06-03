"""Semantic metrics layer — governed metric definitions + a query engine.

Metrics are defined once (here, mirroring the dbt metrics YAML in `warehouse/dbt/metrics/`) and reused
by the API, dashboards, NLQ, and insights. The query engine computes them over the canonical store's
star-schema facts so the same metric means the same thing everywhere.
"""

from app.metrics.engine import MetricEngine, MetricQuery, MetricResult
from app.metrics.definitions import METRICS, MetricDef

__all__ = ["MetricEngine", "MetricQuery", "MetricResult", "METRICS", "MetricDef"]
