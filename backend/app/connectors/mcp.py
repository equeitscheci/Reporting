"""MCP-style connector — treats an MCP server as a modular data adapter.

Each MCP *tool* (or *resource*) is surfaced as a stream: calling the tool returns records. This lets
the platform consume the growing ecosystem of MCP servers (databases, SaaS apps, file stores) with
the same extraction contract as any other connector.

The transport is abstracted behind `_invoke` so it can target stdio or HTTP MCP servers; an injected
callable is used in tests/demo so no live MCP server is required.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from app.connectors.registry import registry
from app.connectors.runtime import TransientError, resilient
from app.connectors.sdk import (
    ConnectionStatus,
    Connector,
    ConnectorConfig,
    FieldSchema,
    Record,
    StreamSchema,
    SyncState,
)

logger = logging.getLogger("insightforge.connectors.mcp")


@registry.register("mcp")
class McpConnector(Connector):
    """Stream config maps to an MCP tool call:

    streams:
      - name: SalesOrders
        path: query_sales_orders        # MCP tool name
        cursor_field: changed_at
        options:
          arguments: { limit: 500 }     # static args passed to the tool
          record_selector: result.rows  # where rows live in the tool response
    """

    def __init__(self, config: ConnectorConfig, secret_resolver: Any | None = None) -> None:
        super().__init__(config, secret_resolver)
        self.server = config.options.get("server")  # command or URL
        self._invoke_fn = config.options.get("_invoke")  # injectable transport

    @resilient(retries=4)
    def _invoke(self, tool: str, arguments: dict[str, Any]) -> Any:
        if self._invoke_fn is not None:
            return self._invoke_fn(tool, arguments)
        # Real transport would speak MCP JSON-RPC here (stdio/http).
        try:
            from app.connectors._mcp_transport import call_tool  # pragma: no cover

            return call_tool(self.server, tool, arguments)
        except ImportError as exc:  # pragma: no cover
            raise TransientError(f"MCP transport unavailable: {exc}") from exc

    def test_connection(self) -> ConnectionStatus:
        try:
            tools = self._invoke("__list_tools__", {})
            return ConnectionStatus(ok=True, discovered_streams=len(tools or []))
        except Exception as exc:  # noqa: BLE001
            return ConnectionStatus(ok=False, message=str(exc))

    def discover(self) -> list[StreamSchema]:
        out = []
        for s in self.config.streams:
            out.append(
                StreamSchema(
                    name=s.name,
                    primary_key=s.primary_key,
                    cursor_field=s.cursor_field,
                    fields=[FieldSchema(name=f, type="string") for f in s.options.get("fields", [])],
                )
            )
        return out

    def read(self, stream: str, state: SyncState) -> Iterator[Record]:
        s = self.stream_config(stream)
        args = dict(s.options.get("arguments", {}))
        cursor = state.cursor_for(stream)
        if s.cursor_field and cursor is not None:
            args[s.options.get("cursor_arg", "since")] = cursor
        resp = self._invoke(s.path or s.name, args)
        rows = _dig(resp, s.options.get("record_selector")) or []
        for row in rows:
            if s.cursor_field and s.cursor_field in row:
                state.advance(stream, row[s.cursor_field])
            yield Record(stream=stream, data=row)


def _dig(obj: Any, path: str | None) -> Any:
    if not path:
        return obj
    cur = obj
    for part in path.split("."):
        cur = cur.get(part) if isinstance(cur, dict) else None
    return cur
