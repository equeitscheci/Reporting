"""Connector registry — plugin-style lookup of connector implementations by `type`.

New source types (including third-party plugins) register here; the rest of the platform only
depends on the `Connector` interface, never concrete classes.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.connectors.sdk import Connector, ConnectorConfig


class ConnectorRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, type[Connector]] = {}

    def register(self, type_name: str) -> Callable[[type[Connector]], type[Connector]]:
        def deco(cls: type[Connector]) -> type[Connector]:
            self._factories[type_name] = cls
            cls.type = type_name
            return cls

        return deco

    def create(
        self, config: ConnectorConfig, secret_resolver: Any | None = None
    ) -> Connector:
        if config.type not in self._factories:
            raise KeyError(
                f"No connector registered for type '{config.type}'. "
                f"Available: {sorted(self._factories)}"
            )
        return self._factories[config.type](config, secret_resolver)

    def available(self) -> list[str]:
        return sorted(self._factories)


registry = ConnectorRegistry()


def load_builtin_connectors() -> None:
    """Import built-in connectors so their @registry.register decorators run."""

    from app.connectors import flatfile, jdbc, mcp, rest  # noqa: F401
    from app.connectors import sample  # noqa: F401
