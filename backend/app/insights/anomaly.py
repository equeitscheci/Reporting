"""Anomaly detection over metric time series.

Method: robust z-score on first differences using median + MAD (median absolute deviation), which is
resistant to the outliers we are trying to find. This flags level shifts like a margin drop or an
inventory spike without assuming a normal distribution. Each anomaly is explainable: it reports the
observed value, the expected band, and the deviation in robust-sigma units.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Anomaly:
    index: int
    label: str  # e.g. the month/period label
    value: float
    expected: float
    lower: float
    upper: float
    z: float
    direction: str  # "spike" | "drop"

    def explain(self, metric_label: str, unit: str) -> str:
        fmt = _fmt(unit)
        return (
            f"{metric_label} at {self.label} was {fmt(self.value)}, "
            f"{'above' if self.direction == 'spike' else 'below'} the expected "
            f"{fmt(self.expected)} (normal range {fmt(self.lower)}–{fmt(self.upper)}); "
            f"deviation ≈ {abs(self.z):.1f}σ."
        )


class AnomalyDetector:
    def __init__(self, threshold: float = 3.0, min_points: int = 4) -> None:
        self.threshold = threshold
        self.min_points = min_points

    def detect(self, labels: list[str], values: list[float]) -> list[Anomaly]:
        if len(values) < self.min_points:
            return []
        arr = np.asarray(values, dtype=float)
        median = float(np.median(arr))
        mad = float(np.median(np.abs(arr - median))) or 1e-9
        # 1.4826 scales MAD to be comparable to standard deviation for normal data.
        robust_sigma = 1.4826 * mad
        lower = median - self.threshold * robust_sigma
        upper = median + self.threshold * robust_sigma

        anomalies: list[Anomaly] = []
        for i, v in enumerate(arr):
            z = (v - median) / (robust_sigma or 1e-9)
            if abs(z) >= self.threshold:
                anomalies.append(
                    Anomaly(
                        index=i,
                        label=labels[i],
                        value=float(v),
                        expected=median,
                        lower=lower,
                        upper=upper,
                        z=float(z),
                        direction="spike" if v > median else "drop",
                    )
                )
        return anomalies


def detect_anomalies(
    labels: list[str], values: list[float], threshold: float = 3.0
) -> list[Anomaly]:
    return AnomalyDetector(threshold=threshold).detect(labels, values)


def _fmt(unit: str):
    if unit == "currency":
        return lambda v: f"${v:,.0f}"
    if unit == "percent":
        return lambda v: f"{v:.1f}%"
    return lambda v: f"{v:,.1f}"
