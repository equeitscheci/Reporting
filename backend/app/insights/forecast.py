"""Forecasting for metric time series (sales, demand).

Baseline: Holt's linear (double exponential smoothing) capturing level + trend, with a naive-mean
fallback for very short series. This is intentionally dependency-light and explainable; the interface
matches what a Prophet/gradient-boosted model would expose so it can be swapped in Phase 2 without
changing callers.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ForecastPoint:
    label: str
    value: float
    lower: float
    upper: float


@dataclass
class Forecast:
    method: str
    history: list[float]
    points: list[ForecastPoint]

    def as_dict(self) -> dict:
        return {
            "method": self.method,
            "history": self.history,
            "forecast": [p.__dict__ for p in self.points],
        }


def _holt(values: np.ndarray, alpha: float, beta: float) -> tuple[float, float, np.ndarray]:
    level = values[0]
    trend = values[1] - values[0] if len(values) > 1 else 0.0
    fitted = np.empty(len(values))
    for t, y in enumerate(values):
        prev_level = level
        fitted[t] = level + trend
        level = alpha * y + (1 - alpha) * (prev_level + trend)
        trend = beta * (level - prev_level) + (1 - beta) * trend
    return level, trend, fitted


def forecast_series(
    history_labels: list[str],
    values: list[float],
    horizon: int = 3,
    alpha: float = 0.5,
    beta: float = 0.3,
) -> Forecast:
    arr = np.asarray(values, dtype=float)
    if len(arr) < 3:
        mean = float(arr.mean()) if len(arr) else 0.0
        pts = [
            ForecastPoint(label=f"+{i + 1}", value=mean, lower=mean, upper=mean)
            for i in range(horizon)
        ]
        return Forecast(method="naive_mean", history=list(arr), points=pts)

    level, trend, fitted = _holt(arr, alpha, beta)
    resid = arr - fitted
    sigma = float(np.std(resid)) if len(resid) > 1 else 0.0

    points: list[ForecastPoint] = []
    for h in range(1, horizon + 1):
        yhat = level + h * trend
        # Prediction interval widens with horizon.
        band = 1.96 * sigma * np.sqrt(h)
        points.append(
            ForecastPoint(
                label=_next_label(history_labels, h),
                value=round(float(yhat), 2),
                lower=round(float(yhat - band), 2),
                upper=round(float(yhat + band), 2),
            )
        )
    return Forecast(method="holt_linear", history=list(arr), points=points)


def _next_label(labels: list[str], h: int) -> str:
    """Best-effort future label. Handles 'YYYY-MM' month labels; else falls back to +h."""

    if labels and len(labels[-1]) == 7 and labels[-1][4] == "-":
        try:
            year, month = map(int, labels[-1].split("-"))
            month += h
            year += (month - 1) // 12
            month = (month - 1) % 12 + 1
            return f"{year:04d}-{month:02d}"
        except ValueError:
            pass
    return f"+{h}"
