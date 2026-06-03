"""API request/response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MetricQueryRequest(BaseModel):
    metric: str
    # None => the metric's default dimensions; [] => grand total (no grouping).
    dimensions: list[str] | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    order_by: str | None = None
    limit: int | None = None


class ReportRunRequest(BaseModel):
    spec: dict[str, Any]


class NLQRequest(BaseModel):
    question: str


class SyncResponse(BaseModel):
    reports: list[dict[str, Any]]
