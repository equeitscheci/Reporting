"""Sample connector — serves bundled in-memory ERP data so the platform runs end-to-end offline.

It emulates a vertical manufacturing ERP (à la ECI verticals) with realistic source-shaped tables.
Used by `insightforge demo` and the test suite. Demonstrates incremental cursors without any network.
"""

from __future__ import annotations

import json
import pathlib
from collections.abc import Iterator
from typing import Any

from app.connectors.registry import registry
from app.connectors.sdk import (
    ConnectionStatus,
    Connector,
    ConnectorConfig,
    FieldSchema,
    Record,
    StreamSchema,
    SyncState,
)

_DATA_DIR = pathlib.Path(__file__).parent / "sample_data"


def _load(stream: str) -> list[dict[str, Any]]:
    path = _DATA_DIR / f"{stream}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text())


@registry.register("sample")
class SampleErpConnector(Connector):
    def test_connection(self) -> ConnectionStatus:
        return ConnectionStatus(ok=True, message="sample ERP", discovered_streams=len(self.config.streams))

    def discover(self) -> list[StreamSchema]:
        out = []
        for s in self.config.streams:
            rows = _load(s.name)
            fields = (
                [FieldSchema(name=k, type=_t(v)) for k, v in rows[0].items()] if rows else []
            )
            out.append(
                StreamSchema(
                    name=s.name,
                    primary_key=s.primary_key,
                    cursor_field=s.cursor_field,
                    fields=fields,
                )
            )
        return out

    def read(self, stream: str, state: SyncState) -> Iterator[Record]:
        s = self.stream_config(stream)
        cursor = state.cursor_for(stream)
        rows = _load(stream)
        if s.cursor_field:
            rows = sorted(rows, key=lambda r: r.get(s.cursor_field) or "")
        for row in rows:
            if s.cursor_field and cursor is not None and (row.get(s.cursor_field) or "") <= cursor:
                continue  # already synced
            if s.cursor_field and s.cursor_field in row:
                state.advance(stream, row[s.cursor_field])
            yield Record(stream=stream, data=row)


def _t(v: Any) -> str:
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int):
        return "integer"
    if isinstance(v, float):
        return "number"
    return "string"
