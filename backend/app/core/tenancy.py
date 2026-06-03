"""Multi-tenant configuration: tenant registry + per-tenant config loading.

Config is Git-backed under `config/tenants/<tenant_id>/` for review/audit, and would be cached in the
`control` schema in production. Each tenant declares: profile, enabled industry packs, connectors,
and mappings. Warehouse isolation is schema-per-tenant (`marts_<tenant_id>`).
"""

from __future__ import annotations

import pathlib
from functools import lru_cache

import yaml
from pydantic import BaseModel, Field

from app.connectors.sdk import ConnectorConfig
from app.core.config import settings
from app.mapping.spec import MappingSpec


class TenantProfile(BaseModel):
    tenant_id: str
    name: str
    industry_packs: list[str] = Field(default_factory=list)
    primary_vertical: str | None = None
    warehouse_schema: str | None = None
    data_residency: str = "us"

    @property
    def schema(self) -> str:
        return self.warehouse_schema or f"marts_{self.tenant_id.replace('-', '_')}"


class TenantConfig(BaseModel):
    profile: TenantProfile
    connectors: list[ConnectorConfig] = Field(default_factory=list)
    mappings: dict[str, MappingSpec] = Field(default_factory=dict)  # keyed by source_system


def _tenant_dir(tenant_id: str) -> pathlib.Path:
    return pathlib.Path(settings.tenants_dir) / tenant_id


def list_tenants() -> list[str]:
    root = pathlib.Path(settings.tenants_dir)
    if not root.exists():
        return []
    return sorted(p.name for p in root.iterdir() if (p / "tenant.yaml").exists())


@lru_cache(maxsize=128)
def load_tenant(tenant_id: str) -> TenantConfig:
    base = _tenant_dir(tenant_id)
    if not (base / "tenant.yaml").exists():
        raise FileNotFoundError(f"No tenant config for '{tenant_id}' at {base}")

    profile = TenantProfile.model_validate(yaml.safe_load((base / "tenant.yaml").read_text()))

    connectors: list[ConnectorConfig] = []
    conn_dir = base / "connectors"
    if conn_dir.exists():
        for f in sorted(conn_dir.glob("*.yaml")):
            raw = yaml.safe_load(f.read_text())
            raw.setdefault("tenant_id", tenant_id)
            connectors.append(ConnectorConfig.model_validate(raw))

    mappings: dict[str, MappingSpec] = {}
    map_dir = base / "mappings"
    if map_dir.exists():
        for f in sorted(map_dir.glob("*.yaml")):
            spec = MappingSpec.from_path(str(f))
            mappings[spec.source_system] = spec

    return TenantConfig(profile=profile, connectors=connectors, mappings=mappings)


def clear_cache() -> None:
    load_tenant.cache_clear()
