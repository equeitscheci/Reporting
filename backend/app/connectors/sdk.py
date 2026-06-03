"""Connector SDK — the single interface every data source implements.

A connector's only job is to *extract* source-shaped records (Bronze layer). Normalization to the
canonical model is the mapping engine's responsibility, keeping connectors thin and reusable.
"""

from __future__ import annotations

import abc
import dataclasses
import datetime as dt
import enum
from collections.abc import Iterator
from typing import Any

from pydantic import BaseModel, Field


class SyncMode(str, enum.Enum):
    FULL_REFRESH = "full_refresh"
    INCREMENTAL = "incremental"
    CDC = "cdc"


class ConnectionStatus(BaseModel):
    """Result of `test_connection`."""

    ok: bool
    message: str = ""
    latency_ms: float | None = None
    discovered_streams: int | None = None


class FieldSchema(BaseModel):
    name: str
    type: str = "string"  # string|integer|number|boolean|date|datetime|object
    nullable: bool = True


class StreamSchema(BaseModel):
    """Describes one extractable stream (e.g. an ERP table or REST resource)."""

    name: str
    primary_key: list[str] = Field(default_factory=list)
    cursor_field: str | None = None  # field used for incremental high-watermark
    supports_cdc: bool = False
    fields: list[FieldSchema] = Field(default_factory=list)


class AuthConfig(BaseModel):
    kind: str = "none"  # none|api_key|basic|static_token|oauth2_client_credentials|oauth2_auth_code
    # Values are *references* (e.g. vault://tenant/source/key), resolved at runtime — never secrets.
    params: dict[str, str] = Field(default_factory=dict)


class StreamConfig(BaseModel):
    name: str
    path: str | None = None  # REST path / table name / file glob
    primary_key: list[str] = Field(default_factory=list)
    cursor_field: str | None = None
    sync_mode: SyncMode = SyncMode.INCREMENTAL
    options: dict[str, Any] = Field(default_factory=dict)  # pagination, record_selector, etc.


class ConnectorConfig(BaseModel):
    """Declarative connector definition (loaded from per-tenant YAML)."""

    id: str
    type: str  # rest|jdbc|flatfile|mcp
    tenant_id: str
    auth: AuthConfig = Field(default_factory=AuthConfig)
    options: dict[str, Any] = Field(default_factory=dict)  # base_url, dsn, root_path, ...
    streams: list[StreamConfig] = Field(default_factory=list)


@dataclasses.dataclass
class Record:
    """A single source-shaped record emitted by a connector (Bronze)."""

    stream: str
    data: dict[str, Any]
    emitted_at: dt.datetime = dataclasses.field(
        default_factory=lambda: dt.datetime.now(dt.timezone.utc)
    )
    # CDC operation if applicable: insert|update|delete
    op: str = "insert"


class SyncState(BaseModel):
    """Persisted between runs to drive incremental/CDC extraction.

    `cursors` holds the last seen high-watermark per stream; `cdc_tokens` holds engine-specific
    change tokens (LSN, SCN, change-tracking version, etc.).
    """

    cursors: dict[str, Any] = Field(default_factory=dict)
    cdc_tokens: dict[str, Any] = Field(default_factory=dict)

    def cursor_for(self, stream: str) -> Any | None:
        return self.cursors.get(stream)

    def advance(self, stream: str, value: Any) -> None:
        prev = self.cursors.get(stream)
        # Monotonic advance — never move the watermark backwards.
        if prev is None or (value is not None and value > prev):
            self.cursors[stream] = value


class Connector(abc.ABC):
    """Base class for all connectors. Subclasses implement the four extraction methods."""

    type: str = "base"

    def __init__(self, config: ConnectorConfig, secret_resolver: Any | None = None) -> None:
        self.config = config
        self._resolve_secret = secret_resolver or (lambda ref: ref)

    @abc.abstractmethod
    def test_connection(self) -> ConnectionStatus:
        """Cheap liveness/auth check."""

    @abc.abstractmethod
    def discover(self) -> list[StreamSchema]:
        """Enumerate available streams and their schemas."""

    @abc.abstractmethod
    def read(self, stream: str, state: SyncState) -> Iterator[Record]:
        """Yield records for one stream, honoring incremental/CDC state.

        Implementations MUST call `state.advance(stream, cursor_value)` as they emit so the next
        run resumes correctly even on partial failure.
        """

    def supports_cdc(self) -> bool:
        return False

    # Helper for subclasses: resolve a vault:// reference to a concrete secret value.
    def secret(self, ref: str | None) -> str | None:
        if ref is None:
            return None
        return self._resolve_secret(ref)

    def stream_config(self, name: str) -> StreamConfig:
        for s in self.config.streams:
            if s.name == name:
                return s
        raise KeyError(f"Stream '{name}' not configured on connector '{self.config.id}'")
