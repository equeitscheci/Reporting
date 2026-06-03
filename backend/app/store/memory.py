"""In-memory, per-tenant canonical store backed by pandas DataFrames.

Upserts by (entity, source_id) using the canonical `row_hash` to skip unchanged rows — the same
semantics a warehouse MERGE would have. Exposes `frame(entity)` so the metrics layer can run
DataFrame queries that mirror the SQL marts.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import pandas as pd

from app.canonical.core import CanonicalRecord


class CanonicalStore:
    def __init__(self) -> None:
        # tenant -> entity -> {source_id: record dict}
        self._data: dict[str, dict[str, dict[str, dict[str, Any]]]] = defaultdict(
            lambda: defaultdict(dict)
        )

    def upsert(self, records: list[CanonicalRecord]) -> dict[str, int]:
        """Upsert canonical records; returns {entity: changed_count}."""

        changed: dict[str, int] = defaultdict(int)
        for rec in records:
            entity = _entity_name(rec)
            bucket = self._data[rec.tenant_id][entity]
            existing = bucket.get(rec.source_id)
            if existing is not None and existing.get("row_hash") == rec.row_hash:
                continue  # unchanged
            bucket[rec.source_id] = rec.model_dump(mode="json")
            changed[entity] += 1
        return dict(changed)

    def count(self, tenant_id: str, entity: str) -> int:
        return len(self._data.get(tenant_id, {}).get(entity, {}))

    def entities(self, tenant_id: str) -> list[str]:
        return sorted(self._data.get(tenant_id, {}).keys())

    def frame(self, tenant_id: str, entity: str) -> pd.DataFrame:
        rows = list(self._data.get(tenant_id, {}).get(entity, {}).values())
        return pd.DataFrame(rows)

    def records(self, tenant_id: str, entity: str) -> list[dict[str, Any]]:
        return list(self._data.get(tenant_id, {}).get(entity, {}).values())


def _entity_name(rec: CanonicalRecord) -> str:
    # Reverse-map the model class to its registry name.
    from app.canonical.registry import ENTITIES

    for name, cls in ENTITIES.items():
        if isinstance(rec, cls) and type(rec) is cls:
            return name
    # Fall back to class name snake-case.
    cls_name = type(rec).__name__
    return "".join(("_" + c.lower()) if c.isupper() else c for c in cls_name).lstrip("_")


# Process-wide store for the API/demo (a real deployment swaps in PostgresStore).
GLOBAL_STORE = CanonicalStore()
