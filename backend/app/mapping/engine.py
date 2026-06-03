"""Mapping engine — turns source-shaped records into validated canonical entities.

Stateless and pure: given a MappingSpec + source records, it yields canonical model instances with
lineage + content hash populated. Validation failures are reported, not silently dropped.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

from app.canonical.core import CanonicalRecord
from app.canonical.registry import get_entity
from app.connectors.sdk import Record
from app.mapping.spec import EntityMapping, MappingSpec
from app.mapping.transforms import apply_transform, safe_eval

logger = logging.getLogger("insightforge.mapping")


class MappingError(Exception):
    pass


@dataclass
class MappingResult:
    records: list[CanonicalRecord] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> int:
        return len(self.records)


class MappingEngine:
    def __init__(self, spec: MappingSpec, tenant_id: str) -> None:
        self.spec = spec
        self.tenant_id = tenant_id
        self._by_stream: dict[str, EntityMapping] = {
            m.source_stream: m for m in spec.entities
        }

    def streams(self) -> list[str]:
        return list(self._by_stream)

    def target_entity(self, stream: str) -> str:
        return self._by_stream[stream].target_entity

    def map_stream(self, stream: str, records: Iterable[Record]) -> MappingResult:
        if stream not in self._by_stream:
            raise MappingError(f"No mapping for source stream '{stream}'")
        ent_map = self._by_stream[stream]
        model_cls = get_entity(ent_map.target_entity)
        result = MappingResult()
        for rec in records:
            row = rec.data
            try:
                if ent_map.filter and not safe_eval(ent_map.filter, row):
                    continue
                obj = self._map_row(ent_map, model_cls, row)
                result.records.append(obj)
            except Exception as exc:  # noqa: BLE001 — collect, never crash the batch
                result.errors.append(
                    {"stream": stream, "source_id": _natural_key(ent_map.source_id, row),
                     "error": str(exc), "row": row}
                )
                logger.warning("Mapping error on %s: %s", stream, exc)
        return result

    def map_records(self, records: Iterable[Record]) -> dict[str, MappingResult]:
        """Map a heterogeneous record stream, grouped by source stream → result."""

        grouped: dict[str, list[Record]] = {}
        for rec in records:
            grouped.setdefault(rec.stream, []).append(rec)
        return {stream: self.map_stream(stream, recs) for stream, recs in grouped.items()}

    # ------------------------------------------------------------------ internals
    def _map_row(
        self, ent_map: EntityMapping, model_cls: type[CanonicalRecord], row: dict[str, Any]
    ) -> CanonicalRecord:
        values: dict[str, Any] = {
            "tenant_id": self.tenant_id,
            "source_system": self.spec.source_system,
            "source_id": _natural_key(ent_map.source_id, row),
        }
        for fm in ent_map.fields:
            if fm.transform is not None:
                val = apply_transform({**fm.transform}, row)
            elif fm.source is not None:
                val = row.get(fm.source)
            else:
                val = None
            if val in (None, "") and fm.default is not None:
                val = fm.default
            if fm.required and val in (None, ""):
                raise MappingError(f"Required field '{fm.target}' missing")
            values[fm.target] = val
        obj = model_cls.model_validate(values)
        return obj.finalize()


def _natural_key(source_id: str | list[str], row: dict[str, Any]) -> str:
    if isinstance(source_id, list):
        return "|".join(str(row.get(k, "")) for k in source_id)
    return str(row.get(source_id, ""))
