"""Secrets vault abstraction.

Connector/mapping configs store *references* like `vault://<tenant>/<source>/<key>`. At runtime the
resolver fetches the concrete value from the configured backend. Values are never persisted in config
or logs. Backends: env vars (dev), local JSON (dev), AWS Secrets Manager / HashiCorp Vault (prod).
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
from typing import Protocol

logger = logging.getLogger("insightforge.secrets")

VAULT_PREFIX = "vault://"


class SecretsBackend(Protocol):
    def get(self, path: str) -> str | None: ...


class EnvBackend:
    """`vault://acme/epicor/client_id` → env var `ACME__EPICOR__CLIENT_ID`."""

    def get(self, path: str) -> str | None:
        key = path.replace("/", "__").replace("-", "_").upper()
        return os.environ.get(key)


class FileBackend:
    """Flat JSON map of `{ "acme/epicor/client_id": "..." }`. Dev only."""

    def __init__(self, file_path: str) -> None:
        self._path = pathlib.Path(file_path)
        self._cache: dict[str, str] | None = None

    def _load(self) -> dict[str, str]:
        if self._cache is None:
            if self._path.exists():
                self._cache = json.loads(self._path.read_text())
            else:
                self._cache = {}
        return self._cache

    def get(self, path: str) -> str | None:
        return self._load().get(path)


class AwsSecretsManagerBackend:  # pragma: no cover - infra
    def __init__(self, region: str | None = None) -> None:
        import boto3  # type: ignore

        self._client = boto3.client("secretsmanager", region_name=region)

    def get(self, path: str) -> str | None:
        try:
            resp = self._client.get_secret_value(SecretId=path)
            return resp.get("SecretString")
        except Exception as exc:  # noqa: BLE001
            logger.error("Secrets Manager fetch failed for %s: %s", path, exc)
            return None


class SecretResolver:
    def __init__(self, backend: SecretsBackend) -> None:
        self._backend = backend

    def resolve(self, ref: str | None) -> str | None:
        """Resolve a `vault://` reference; pass through non-references unchanged."""

        if ref is None:
            return None
        if not ref.startswith(VAULT_PREFIX):
            return ref  # literal value (acceptable for non-secret options)
        path = ref[len(VAULT_PREFIX) :]
        val = self._backend.get(path)
        if val is None:
            logger.warning("Secret not found for reference (path redacted)")
        return val

    def __call__(self, ref: str | None) -> str | None:
        return self.resolve(ref)


def build_resolver(backend: str, file_path: str | None = None) -> SecretResolver:
    if backend == "env":
        return SecretResolver(EnvBackend())
    if backend == "file":
        return SecretResolver(FileBackend(file_path or "secrets.dev.json"))
    if backend == "aws_secrets_manager":
        return SecretResolver(AwsSecretsManagerBackend())
    raise ValueError(f"Unsupported secrets backend: {backend}")
