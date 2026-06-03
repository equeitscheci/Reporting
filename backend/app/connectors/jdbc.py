"""JDBC/ODBC connector (SQLAlchemy-backed) for SQL Server, MySQL, Postgres, Oracle.

Incremental: high-watermark on a `cursor_field` column.
CDC: pluggable strategy per engine — SQL Server Change Tracking, Postgres logical/`xmin`,
Oracle `ORA_ROWSCN`. The strategy interface is defined here; concrete SQL is engine-specific and
selected by `options.cdc_strategy`.
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
    StreamConfig,
    StreamSchema,
    SyncState,
)

logger = logging.getLogger("insightforge.connectors.jdbc")


# CDC strategies map an engine to the SQL needed to read changes since a token.
CDC_STRATEGIES = {
    # SQL Server Change Tracking
    "mssql_ct": {
        "changes_sql": (
            "SELECT ct.*, t.* FROM CHANGETABLE(CHANGES {table}, {token}) ct "
            "LEFT JOIN {table} t ON t.{pk} = ct.{pk}"
        ),
        "token_sql": "SELECT CHANGE_TRACKING_CURRENT_VERSION() AS token",
        "op_column": "SYS_CHANGE_OPERATION",  # I/U/D
    },
    # Postgres system column transaction id (coarse CDC fallback)
    "postgres_xmin": {
        "changes_sql": "SELECT *, xmin::text::bigint AS _xmin FROM {table} WHERE xmin::text::bigint > {token}",
        "token_sql": "SELECT pg_snapshot_xmin(pg_current_snapshot())::text::bigint AS token",
        "op_column": None,
    },
    # Oracle row system change number
    "oracle_scn": {
        "changes_sql": "SELECT t.*, ORA_ROWSCN AS _scn FROM {table} t WHERE ORA_ROWSCN > {token}",
        "token_sql": "SELECT CURRENT_SCN AS token FROM V$DATABASE",
        "op_column": None,
    },
}


@registry.register("jdbc")
class JdbcConnector(Connector):
    def __init__(self, config: ConnectorConfig, secret_resolver: Any | None = None) -> None:
        super().__init__(config, secret_resolver)
        # DSN may itself reference secrets, e.g. postgresql://user:vault://...@host/db
        self.dsn: str = self.secret(config.options.get("dsn")) or config.options.get("dsn", "")
        self._engine = None  # lazy
        self._fetch_size = int(config.options.get("fetch_size", 5000))
        self._injected_rows = config.options.get("_rows")  # for tests/sample mode

    def _get_engine(self):  # noqa: ANN202
        if self._engine is None:
            from sqlalchemy import create_engine

            self._engine = create_engine(self.dsn, pool_pre_ping=True)
        return self._engine

    @resilient(retries=4)
    def _execute(self, sql: str, params: dict | None = None) -> list[dict[str, Any]]:
        # Sample/test path: serve injected rows without a real DB.
        if self._injected_rows is not None:
            return list(self._injected_rows.get(sql, []))
        try:
            from sqlalchemy import text

            with self._get_engine().connect() as conn:
                conn = conn.execution_options(stream_results=True)
                result = conn.execute(text(sql), params or {})
                return [dict(r._mapping) for r in result]
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).lower()
            if any(k in msg for k in ("timeout", "connection", "deadlock", "temporarily")):
                raise TransientError(str(exc)) from exc
            raise

    def test_connection(self) -> ConnectionStatus:
        import time

        start = time.monotonic()
        try:
            self._execute("SELECT 1")
            return ConnectionStatus(
                ok=True,
                latency_ms=(time.monotonic() - start) * 1000,
                discovered_streams=len(self.config.streams),
            )
        except Exception as exc:  # noqa: BLE001
            return ConnectionStatus(ok=False, message=str(exc))

    def discover(self) -> list[StreamSchema]:
        out = []
        for s in self.config.streams:
            fields: list[FieldSchema] = []
            try:
                rows = self._execute(f"SELECT * FROM {s.path} LIMIT 1")
                if rows:
                    fields = [
                        FieldSchema(name=k, type=_sql_type(v)) for k, v in rows[0].items()
                    ]
            except Exception:  # noqa: BLE001
                pass
            out.append(
                StreamSchema(
                    name=s.name,
                    primary_key=s.primary_key,
                    cursor_field=s.cursor_field,
                    supports_cdc=bool(s.options.get("cdc_strategy")),
                    fields=fields,
                )
            )
        return out

    def supports_cdc(self) -> bool:
        return any(s.options.get("cdc_strategy") for s in self.config.streams)

    def read(self, stream: str, state: SyncState) -> Iterator[Record]:
        s = self.stream_config(stream)
        strat = s.options.get("cdc_strategy")
        if strat:
            yield from self._read_cdc(s, state, strat)
        else:
            yield from self._read_incremental(s, state)

    def _read_incremental(self, s: StreamConfig, state: SyncState) -> Iterator[Record]:
        cursor = state.cursor_for(s.name)
        where = ""
        params: dict[str, Any] = {}
        if s.cursor_field and cursor is not None:
            where = f" WHERE {s.cursor_field} > :cursor"
            params["cursor"] = cursor
        order = f" ORDER BY {s.cursor_field}" if s.cursor_field else ""
        sql = f"SELECT * FROM {s.path}{where}{order}"
        for row in self._execute(sql, params):
            if s.cursor_field and s.cursor_field in row:
                state.advance(s.name, row[s.cursor_field])
            yield Record(stream=s.name, data=row)

    def _read_cdc(self, s: StreamConfig, state: SyncState, strat: str) -> Iterator[Record]:
        spec = CDC_STRATEGIES[strat]
        token = state.cdc_tokens.get(s.name, 0)
        pk = s.primary_key[0] if s.primary_key else "id"
        sql = spec["changes_sql"].format(table=s.path, token=token, pk=pk)
        op_col = spec["op_column"]
        for row in self._execute(sql):
            op = _map_op(row.get(op_col)) if op_col else "upsert"
            yield Record(stream=s.name, data=row, op=op)
        # Advance the change token for the next run.
        new_token = self._execute(spec["token_sql"])
        if new_token:
            state.cdc_tokens[s.name] = new_token[0]["token"]


def _map_op(raw: Any) -> str:
    return {"I": "insert", "U": "update", "D": "delete"}.get(str(raw), "upsert")


def _sql_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return "string"
