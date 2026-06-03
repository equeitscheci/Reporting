"""API smoke tests via FastAPI TestClient (auth disabled in dev)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
HEADERS = {"X-Tenant-Id": "acme-mfg", "X-Roles": "owner"}


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_list_tenants():
    r = client.get("/tenants", headers=HEADERS)
    assert r.status_code == 200
    assert "acme-mfg" in r.json()["tenants"]


def test_sync_then_query_and_insights():
    r = client.post("/sync", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["reports"]

    r = client.post(
        "/metrics/query",
        headers=HEADERS,
        json={"metric": "revenue", "dimensions": ["month"]},
    )
    assert r.status_code == 200
    assert r.json()["rows"]

    r = client.get("/insights", headers=HEADERS)
    assert r.status_code == 200
    assert any(i["severity"] == "critical" for i in r.json()["insights"])


def test_nlq_endpoint():
    client.post("/sync", headers=HEADERS)
    r = client.post("/insights/ask", headers=HEADERS, json={"question": "why did margins drop last month?"})
    assert r.status_code == 200
    assert r.json()["resolved_query"]["metric"] == "gross_margin_pct"


def test_rbac_blocks_viewer_from_sync():
    r = client.post("/sync", headers={"X-Tenant-Id": "acme-mfg", "X-Roles": "viewer"})
    assert r.status_code == 403
