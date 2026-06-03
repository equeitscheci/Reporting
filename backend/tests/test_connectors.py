"""Connector SDK + built-in connector behavior."""

from __future__ import annotations

from app.connectors.registry import load_builtin_connectors, registry
from app.connectors.runtime import (
    CircuitBreaker,
    CircuitOpenError,
    TransientError,
    build_auth,
    resilient,
)
from app.connectors.sdk import (
    AuthConfig,
    ConnectorConfig,
    StreamConfig,
    SyncState,
)

load_builtin_connectors()


def test_registry_has_builtin_types():
    types = registry.available()
    for t in ("rest", "jdbc", "flatfile", "mcp", "sample"):
        assert t in types


def test_sync_state_monotonic_advance():
    s = SyncState()
    s.advance("orders", "2026-01-01")
    s.advance("orders", "2025-12-01")  # older — must not move backwards
    assert s.cursor_for("orders") == "2026-01-01"
    s.advance("orders", "2026-02-01")
    assert s.cursor_for("orders") == "2026-02-01"


def test_resilient_retries_then_succeeds():
    calls = {"n": 0}

    @resilient(retries=3, base_delay=0.0, jitter=0.0)
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise TransientError("boom")
        return "ok"

    assert flaky() == "ok"
    assert calls["n"] == 3


def test_circuit_breaker_opens():
    cb = CircuitBreaker(failure_threshold=2, reset_timeout=999)
    cb.record_failure()
    cb.record_failure()
    try:
        cb.before_call()
        assert False, "expected CircuitOpenError"
    except CircuitOpenError:
        pass


def test_build_auth_oauth_caches_token():
    posts = {"n": 0}

    def fake_post(url, data):
        posts["n"] += 1
        return {"access_token": "tok123", "expires_in": 3600}

    from app.connectors.runtime import OAuth2ClientCredentials

    auth = OAuth2ClientCredentials(
        "https://x/token", "cid", "secret", http_post=fake_post
    )
    assert auth.headers()["Authorization"] == "Bearer tok123"
    auth.headers()  # second call should reuse cached token
    assert posts["n"] == 1


def test_sample_connector_incremental():
    cfg = ConnectorConfig(
        id="t", type="sample", tenant_id="acme-mfg", auth=AuthConfig(kind="none"),
        streams=[StreamConfig(name="customers", primary_key=["CustNum"],
                              cursor_field="ChangedDate")],
    )
    conn = registry.create(cfg)
    assert conn.test_connection().ok
    state = SyncState()
    first = list(conn.read("customers", state))
    assert len(first) == 8
    # Second run with advanced cursor yields nothing new.
    second = list(conn.read("customers", state))
    assert second == []


def test_rest_pagination_with_injected_client():
    pages = {
        1: [{"OrderNum": i, "ChangedDate": f"2026-01-{i:02d}"} for i in range(1, 3)],
        2: [{"OrderNum": i, "ChangedDate": f"2026-01-{i:02d}"} for i in range(3, 4)],
    }

    def client(url, params, headers):
        page = params.get("page", 1)
        return 200, {"results": pages.get(page, [])}

    cfg = ConnectorConfig(
        id="r", type="rest", tenant_id="t",
        options={"base_url": "https://erp", "_client": client},
        streams=[StreamConfig(
            name="SalesOrders", path="/orders", cursor_field="ChangedDate",
            options={"record_selector": "results", "pagination": {"kind": "page", "size": 2}},
        )],
    )
    conn = registry.create(cfg)
    rows = list(conn.read("SalesOrders", SyncState()))
    assert len(rows) == 3
