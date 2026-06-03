"""Mapping specification models (loaded from per-tenant YAML).

A MappingSpec is versioned per (tenant, source_system) so ERP onboarding == authoring config.
"""

from __future__ import annotations

from typing import Any

import yaml
from pydantic import BaseModel, Field


class FieldMapping(BaseModel):
    """How to populate one canonical field from a source record.

    Either `source` (direct field) or `transform` (op + args). `default` applies when the result is
    None/missing.
    """

    target: str
    source: str | None = None
    transform: dict[str, Any] | None = None
    default: Any | None = None
    required: bool = False


class EntityMapping(BaseModel):
    source_stream: str
    target_entity: str
    source_id: str | list[str]  # field(s) forming the source natural key
    fields: list[FieldMapping] = Field(default_factory=list)
    filter: str | None = None  # optional expression; rows evaluating falsey are skipped


class MappingSpec(BaseModel):
    source_system: str
    version: int = 1
    entities: list[EntityMapping] = Field(default_factory=list)

    @classmethod
    def from_yaml(cls, text: str) -> "MappingSpec":
        raw = yaml.safe_load(text)
        # Support a compact dict form for `fields` (target: source) alongside the verbose list form.
        for ent in raw.get("entities", []):
            fields = ent.get("fields")
            if isinstance(fields, dict):
                ent["fields"] = [
                    _normalize_field(target, val) for target, val in fields.items()
                ]
        return cls.model_validate(raw)

    @classmethod
    def from_path(cls, path: str) -> "MappingSpec":
        with open(path, encoding="utf-8") as fh:
            return cls.from_yaml(fh.read())


def _normalize_field(target: str, val: Any) -> dict[str, Any]:
    if isinstance(val, str):
        return {"target": target, "source": val}
    if isinstance(val, dict):
        return {"target": target, **val}
    raise ValueError(f"Invalid field mapping for '{target}': {val!r}")
