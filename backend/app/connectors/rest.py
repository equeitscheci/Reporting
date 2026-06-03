"""REST API connector — paginated, rate-limit aware, incremental.

Handles the pagination strategies seen across ERP/CRM/SaaS REST APIs:
cursor, page-number, offset/limit, and RFC-5988 Link headers. Record selection via a JSONPath-lite
`record_selector` (dotted path). Incremental via a `cursor_field` filter parameter.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from app.connectors.registry import registry
from app.connectors.runtime import (
    CircuitBreaker,
    TransientError,
    build_auth,
    resilient,
)
from app.connectors.sdk import (
    ConnectionStatus,
    Connector,
    ConnectorConfig,
    FieldSchema,
    Record,
    StreamConfig,
    StreamSchema,
    SyncState,
)

logger = logging.getLogger("insightforge.connectors.rest")


def _dig(obj: Any, path: str | None) -> Any:
    """Resolve a dotted path within nested dicts/lists. Empty path returns obj unchanged."""

    if not path:
        return obj
    cur = obj
    for part in path.split("."):
        if isinstance(cur, list):
            cur = [(_dig(item, part)) for item in cur]
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


@registry.register("rest")
class RestConnector(Connector):
    def __init__(self, config: ConnectorConfig, secret_resolver: Any | None = None) -> None:
        super().__init__(config, secret_resolver)
        self.base_url: str = config.options.get("base_url", "").rstrip("/")
        self.timeout: float = float(config.options.get("timeout", 30))
        self._breaker = CircuitBreaker()
        # Resolve auth references → concrete values via the secret resolver.
        resolved = {k: self.secret(v) for k, v in config.auth.params.items()}
        self._auth = build_auth(config.auth.kind, {k: v for k, v in resolved.items() if v})
        # Injectable HTTP client (real httpx by default; overridden in tests/sample mode).
        self._client = config.options.get("_client")

    # ------------------------------------------------------------------ http
    @resilient(retries=5)
    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        self._breaker.before_call()
        try:
            if self._client is not None:
                status, body = self._client(url, params=params, headers=self._auth.headers())
            else:
                import httpx

                resp = httpx.get(
                    url,
                    params={**self._auth.params(), **params},
                    headers=self._auth.headers(),
                    timeout=self.timeout,
                )
                status, body = resp.status_code, (resp.json() if resp.content else {})
                resp_headers = dict(resp.headers)
                body = {"__status": status, "__headers": resp_headers, "body": body}
                if status == 429 or status >= 500:
                    raise TransientError(f"HTTP {status} from {url}")
                resp.raise_for_status()
                self._breaker.record_success()
                return body
            if status == 429 or status >= 500:
                raise TransientError(f"HTTP {status} from {url}")
            self._breaker.record_success()
            return {"__status": status, "__headers": {}, "body": body}
        except TransientError:
            self._breaker.record_failure()
            raise

    # ------------------------------------------------------------------ sdk
    def test_connection(self) -> ConnectionStatus:
        import time

        start = time.monotonic()
        try:
            if self.config.streams:
                s = self.config.streams[0]
                self._get(f"{self.base_url}{s.path}", {"$top": 1})
            return ConnectionStatus(
                ok=True,
                latency_ms=(time.monotonic() - start) * 1000,
                discovered_streams=len(self.config.streams),
            )
        except Exception as exc:  # noqa: BLE001
            return ConnectionStatus(ok=False, message=str(exc))

    def discover(self) -> list[StreamSchema]:
        out: list[StreamSchema] = []
        for s in self.config.streams:
            # Sample one page to infer fields.
            fields: list[FieldSchema] = []
            try:
                page = self._get(f"{self.base_url}{s.path}", self._page_params(s, None, 1))
                rows = _dig(page["body"], s.options.get("record_selector")) or []
                if rows:
                    fields = [_infer_field(k, v) for k, v in rows[0].items()]
            except Exception:  # noqa: BLE001
                pass
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
        page_token: Any = None
        page_num = 1
        url = f"{self.base_url}{s.path}"
        while True:
            params = self._page_params(s, cursor, page_num, page_token)
            resp = self._get(url, params)
            body = resp["body"]
            rows = _dig(body, s.options.get("record_selector")) or []
            for row in rows:
                if s.cursor_field and s.cursor_field in row:
                    state.advance(stream, row[s.cursor_field])
                yield Record(stream=stream, data=row)
            page_token, has_more = self._next_page(s, resp, rows, page_num)
            if not has_more:
                break
            page_num += 1

    # ------------------------------------------------------------------ pagination
    def _page_params(
        self,
        s: StreamConfig,
        cursor: Any,
        page_num: int,
        page_token: Any = None,
    ) -> dict[str, Any]:
        pg = s.options.get("pagination", {})
        kind = pg.get("kind", "page")
        size = pg.get("size", 100)
        params: dict[str, Any] = dict(s.options.get("query_params", {}))
        if kind == "page":
            params[pg.get("page_param", "page")] = page_num
            params[pg.get("size_param", "per_page")] = size
        elif kind == "offset":
            params[pg.get("offset_param", "offset")] = (page_num - 1) * size
            params[pg.get("limit_param", "limit")] = size
        elif kind == "cursor" and page_token is not None:
            params[pg.get("cursor_param", "cursor")] = page_token
        # Incremental filter.
        if s.cursor_field and cursor is not None:
            tmpl = s.options.get("incremental_param", "{field}>{value}")
            params[pg.get("filter_param", "filter")] = tmpl.format(
                field=s.cursor_field, value=cursor
            )
        return params

    def _next_page(
        self, s: StreamConfig, resp: dict[str, Any], rows: list, page_num: int
    ) -> tuple[Any, bool]:
        pg = s.options.get("pagination", {})
        kind = pg.get("kind", "page")
        if not rows:
            return None, False
        if kind in ("page", "offset"):
            return None, len(rows) >= pg.get("size", 100)
        if kind == "cursor":
            token = _dig(resp["body"], pg.get("next_cursor_path", "next_cursor"))
            return token, token is not None
        if kind == "link":
            link = resp.get("__headers", {}).get("link") or resp.get("__headers", {}).get("Link")
            return None, bool(link and 'rel="next"' in link)
        return None, False


def _infer_field(name: str, value: Any) -> FieldSchema:
    if isinstance(value, bool):
        t = "boolean"
    elif isinstance(value, int):
        t = "integer"
    elif isinstance(value, float):
        t = "number"
    elif isinstance(value, dict):
        t = "object"
    else:
        t = "string"
    return FieldSchema(name=name, type=t)
