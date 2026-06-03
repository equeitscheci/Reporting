"""REST API endpoints.

Surface area (all tenant-scoped via the `X-Tenant-Id` header / JWT claim):
  GET  /tenants                         list tenants
  GET  /tenants/{id}                    tenant profile + enabled packs
  GET  /connectors                      configured connectors for the tenant
  POST /connectors/{id}/test            test connection
  POST /sync                            run the ELT pipeline for the tenant
  GET  /metrics                         metric catalog (semantic layer)
  POST /metrics/query                   execute a metric query (slice/filter)
  POST /reports/run                     execute a saved/ad-hoc report spec
  GET  /insights                        scan metrics → anomalies/forecasts/recs
  POST /insights/ask                    natural-language query
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.schemas import (
    MetricQueryRequest,
    NLQRequest,
    ReportRunRequest,
    SyncResponse,
)
from app.core.security import Principal, get_principal
from app.core.tenancy import list_tenants, load_tenant
from app.insights.ai_studio import answer_with_optional_ai_studio
from app.insights.engine import InsightsEngine
from app.insights.nlq import NLQueryEngine
from app.insights.recommendations import generate_recommendations
from app.metrics.definitions import METRICS, metrics_for_industry
from app.metrics.engine import MetricQuery
from app.reports.runner import run_report_spec
from app.services import metric_engine, secret_resolver, seed_tenant

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/tenants")
def get_tenants(principal: Principal = Depends(get_principal)) -> dict[str, Any]:
    principal.require("config:read")
    return {"tenants": list_tenants()}


@router.get("/tenants/{tenant_id}")
def get_tenant(tenant_id: str, principal: Principal = Depends(get_principal)) -> dict[str, Any]:
    principal.require("config:read")
    cfg = load_tenant(tenant_id)
    return {
        "profile": cfg.profile.model_dump(),
        "connectors": [c.id for c in cfg.connectors],
        "mappings": list(cfg.mappings),
        "schema": cfg.profile.schema,
    }


@router.get("/connectors")
def get_connectors(principal: Principal = Depends(get_principal)) -> dict[str, Any]:
    principal.require("config:read")
    cfg = load_tenant(principal.tenant_id)
    return {
        "connectors": [
            {"id": c.id, "type": c.type, "streams": [s.name for s in c.streams]}
            for c in cfg.connectors
        ]
    }


@router.post("/connectors/{connector_id}/test")
def test_connector(
    connector_id: str, principal: Principal = Depends(get_principal)
) -> dict[str, Any]:
    principal.require("config:read")
    from app.connectors.registry import registry

    cfg = load_tenant(principal.tenant_id)
    match = next((c for c in cfg.connectors if c.id == connector_id), None)
    if match is None:
        raise HTTPException(404, f"Connector '{connector_id}' not found")
    connector = registry.create(match, secret_resolver)
    return connector.test_connection().model_dump()


@router.post("/sync", response_model=SyncResponse)
def run_sync(principal: Principal = Depends(get_principal)) -> SyncResponse:
    principal.require("pipeline:run")
    _, reports = seed_tenant(principal.tenant_id)
    return SyncResponse(reports=[r.as_dict() for r in reports])


@router.get("/metrics")
def get_metrics(principal: Principal = Depends(get_principal)) -> dict[str, Any]:
    principal.require("config:read")
    cfg = load_tenant(principal.tenant_id)
    industry = cfg.profile.primary_vertical
    return {"metrics": [m.as_dict() for m in metrics_for_industry(industry)]}


@router.post("/metrics/query")
def query_metric(
    req: MetricQueryRequest, principal: Principal = Depends(get_principal)
) -> dict[str, Any]:
    principal.require("data:read")
    if req.metric not in METRICS:
        raise HTTPException(400, f"Unknown metric '{req.metric}'")
    result = metric_engine.query(
        principal.tenant_id,
        MetricQuery(
            metric=req.metric,
            dimensions=req.dimensions,
            filters=req.filters,
            order_by=req.order_by,
            limit=req.limit,
        ),
    )
    return result.as_dict()


@router.post("/reports/run")
def run_report(
    req: ReportRunRequest, principal: Principal = Depends(get_principal)
) -> dict[str, Any]:
    principal.require("data:read")
    return run_report_spec(principal.tenant_id, req.spec, metric_engine)


@router.get("/insights")
def get_insights(principal: Principal = Depends(get_principal)) -> dict[str, Any]:
    principal.require("insights:read")
    cfg = load_tenant(principal.tenant_id)
    engine = InsightsEngine(metric_engine)
    insights = engine.scan(principal.tenant_id, industry=cfg.profile.primary_vertical)
    return {"insights": [i.as_dict() for i in insights]}


@router.get("/insights/recommendations")
def get_recommendations(principal: Principal = Depends(get_principal)) -> dict[str, Any]:
    principal.require("insights:read")
    cfg = load_tenant(principal.tenant_id)
    return {"recommendations": generate_recommendations(
        principal.tenant_id, metric_engine, cfg.profile.primary_vertical)}


@router.post("/insights/ask")
def ask(req: NLQRequest, principal: Principal = Depends(get_principal)) -> dict[str, Any]:
    principal.require("insights:read")
    cfg = load_tenant(principal.tenant_id)
    nlq = NLQueryEngine(metric_engine)
    local_answer = nlq.answer(principal.tenant_id, req.question)
    return answer_with_optional_ai_studio(
        tenant_id=principal.tenant_id,
        question=req.question,
        local_answer=local_answer,
        industry=cfg.profile.primary_vertical,
    )
