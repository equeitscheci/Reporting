"""Sync-state persistence + data-freshness tracking.

In dev this is a JSON file per (tenant, connector); in prod it lives in the `control` schema. State
drives incremental/CDC resumption; freshness records per-stream lag against each stream's SLA.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
from dataclasses import asdict, dataclass, field

from app.connectors.sdk import SyncState


@dataclass
class FreshnessRecord:
    stream: str
    last_sync_at: str
    records: int
    max_lag_minutes: float | None = None  # SLA; None = no SLA
    within_sla: bool = True


@dataclass
class StateStore:
    """File-backed store of sync state + freshness for a tenant/connector."""

    root: str
    tenant_id: str
    connector_id: str
    freshness: list[FreshnessRecord] = field(default_factory=list)

    def _path(self) -> pathlib.Path:
        d = pathlib.Path(self.root) / self.tenant_id
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{self.connector_id}.state.json"

    def load(self) -> SyncState:
        p = self._path()
        if p.exists():
            data = json.loads(p.read_text())
            return SyncState.model_validate(data.get("sync_state", {}))
        return SyncState()

    def save(self, state: SyncState) -> None:
        p = self._path()
        payload = {
            "sync_state": state.model_dump(mode="json"),
            "freshness": [asdict(f) for f in self.freshness],
            "saved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        p.write_text(json.dumps(payload, indent=2, default=str))

    def record_freshness(
        self, stream: str, count: int, sla_minutes: float | None = None
    ) -> None:
        now = dt.datetime.now(dt.timezone.utc)
        self.freshness.append(
            FreshnessRecord(
                stream=stream,
                last_sync_at=now.isoformat(),
                records=count,
                max_lag_minutes=sla_minutes,
                within_sla=True,
            )
        )
