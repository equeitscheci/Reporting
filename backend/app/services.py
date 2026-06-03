"""Shared service singletons + the demo pipeline used by both the API and the CLI.

Keeps wiring in one place: the global store, metric engine, secret resolver, and a `seed_tenant`
helper that runs the full extract → map → validate → load path for a tenant's configured connectors.
"""

from __future__ import annotations

import atexit
import shutil
import tempfile

from app.connectors.registry import load_builtin_connectors
from app.core.config import settings
from app.core.secrets import build_resolver
from app.core.tenancy import TenantConfig, load_tenant
from app.metrics.engine import MetricEngine
from app.pipeline.sync import SyncReport, SyncRunner
from app.store.memory import GLOBAL_STORE

load_builtin_connectors()

secret_resolver = build_resolver(settings.secrets_backend, settings.secrets_file)
store = GLOBAL_STORE
metric_engine = MetricEngine(store)

# The in-memory store is ephemeral (lost on process restart), so its incremental sync state must be
# too — otherwise persisted cursors would make connectors skip records into an empty store. A real
# deployment uses PostgresStore + DB-backed state where persistence is correct and desirable.
_STATE_ROOT = tempfile.mkdtemp(prefix="insightforge-state-")
atexit.register(lambda: shutil.rmtree(_STATE_ROOT, ignore_errors=True))


def seed_tenant(tenant_id: str) -> tuple[TenantConfig, list[SyncReport]]:
    """Load a tenant's config and run all its connectors into the store."""

    tenant = load_tenant(tenant_id)
    runner = SyncRunner(store=store, secret_resolver=secret_resolver, state_root=_STATE_ROOT)
    reports = runner.run_tenant(tenant)
    metric_engine.invalidate(tenant_id)
    return tenant, reports
