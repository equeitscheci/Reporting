"""Sync runner — orchestrates extract → map → validate → load for a tenant connector.

This is the unit an Airflow task wraps. It is connector- and source-agnostic: it depends only on the
SDK and the mapping engine, so a new ERP requires no changes here.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field
from typing import Any

from app.connectors.registry import registry
from app.connectors.sdk import ConnectorConfig
from app.core.tenancy import TenantConfig
from app.mapping.engine import MappingEngine
from app.mapping.spec import MappingSpec
from app.pipeline.state import StateStore
from app.pipeline.validation import Validator
from app.store.memory import CanonicalStore

logger = logging.getLogger("insightforge.pipeline")


@dataclass
class StreamReport:
    stream: str
    entity: str
    extracted: int = 0
    mapped: int = 0
    mapping_errors: int = 0
    validated: int = 0
    quarantined: int = 0
    loaded: int = 0


@dataclass
class SyncReport:
    tenant_id: str
    connector_id: str
    started_at: str = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())
    finished_at: str | None = None
    streams: list[StreamReport] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "connector_id": self.connector_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "streams": [s.__dict__ for s in self.streams],
            "totals": {
                "extracted": sum(s.extracted for s in self.streams),
                "loaded": sum(s.loaded for s in self.streams),
                "quarantined": sum(s.quarantined for s in self.streams),
            },
            "errors": self.errors[:50],
        }


class SyncRunner:
    def __init__(
        self,
        store: CanonicalStore,
        secret_resolver: Any | None = None,
        state_root: str = ".state",
        validator: Validator | None = None,
    ) -> None:
        self.store = store
        self.secret_resolver = secret_resolver
        self.state_root = state_root
        self.validator = validator or Validator()

    def run_connector(
        self,
        connector_cfg: ConnectorConfig,
        mapping: MappingSpec,
    ) -> SyncReport:
        report = SyncReport(tenant_id=connector_cfg.tenant_id, connector_id=connector_cfg.id)
        connector = registry.create(connector_cfg, self.secret_resolver)
        engine = MappingEngine(mapping, connector_cfg.tenant_id)
        state_store = StateStore(self.state_root, connector_cfg.tenant_id, connector_cfg.id)
        state = state_store.load()

        for stream_cfg in connector_cfg.streams:
            stream = stream_cfg.name
            if stream not in engine.streams():
                logger.info("Skipping stream '%s' — no mapping defined", stream)
                continue
            entity = engine.target_entity(stream)
            sr = StreamReport(stream=stream, entity=entity)
            try:
                raw = list(connector.read(stream, state))
                sr.extracted = len(raw)

                result = engine.map_stream(stream, raw)
                sr.mapped = result.ok
                sr.mapping_errors = len(result.errors)
                report.errors.extend(result.errors)

                passed, quarantined, vreport = self.validator.validate(entity, result.records)
                sr.validated = vreport.passed
                sr.quarantined = vreport.quarantined

                changed = self.store.upsert(passed)
                sr.loaded = changed.get(entity, 0)

                state_store.record_freshness(stream, sr.loaded)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Stream '%s' failed", stream)
                report.errors.append({"stream": stream, "error": str(exc)})
            report.streams.append(sr)

        state_store.save(state)
        report.finished_at = dt.datetime.now(dt.timezone.utc).isoformat()
        return report

    def run_tenant(self, tenant: TenantConfig) -> list[SyncReport]:
        reports = []
        for conn in tenant.connectors:
            mapping = tenant.mappings.get(conn.options.get("source_system", conn.type))
            if mapping is None and len(tenant.mappings) == 1:
                mapping = next(iter(tenant.mappings.values()))
            if mapping is None:
                logger.warning("No mapping for connector %s; skipping", conn.id)
                continue
            reports.append(self.run_connector(conn, mapping))
        return reports
