"""Connector framework: SDK interface, runtime utilities, and built-in connectors."""

from app.connectors.registry import ConnectorRegistry, registry
from app.connectors.sdk import (
    ConnectionStatus,
    Connector,
    ConnectorConfig,
    Record,
    StreamSchema,
    SyncMode,
    SyncState,
)

__all__ = [
    "Connector",
    "ConnectorConfig",
    "ConnectionStatus",
    "StreamSchema",
    "Record",
    "SyncMode",
    "SyncState",
    "ConnectorRegistry",
    "registry",
]
