"""Insights & intelligence layer — anomaly detection, forecasting, NLQ, recommendations.

All outputs are explainable: every insight carries the evidence that produced it and concrete
recommended actions. The approach is a hybrid of deterministic rules and lightweight statistics/ML so
results are reproducible and auditable (a hard requirement for SMB finance/ops users).
"""

from app.insights.anomaly import AnomalyDetector, detect_anomalies
from app.insights.engine import Insight, InsightsEngine
from app.insights.forecast import forecast_series
from app.insights.nlq import NLQuery, NLQueryEngine
from app.insights.recommendations import generate_recommendations

__all__ = [
    "Insight",
    "InsightsEngine",
    "AnomalyDetector",
    "detect_anomalies",
    "forecast_series",
    "NLQuery",
    "NLQueryEngine",
    "generate_recommendations",
]
