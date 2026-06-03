"""Declarative mapping engine: source records → canonical entities."""

from app.mapping.engine import MappingEngine, MappingError
from app.mapping.spec import EntityMapping, FieldMapping, MappingSpec

__all__ = ["MappingEngine", "MappingError", "MappingSpec", "EntityMapping", "FieldMapping"]
