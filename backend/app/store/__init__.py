"""Warehouse store abstraction.

`CanonicalStore` is the load target for the pipeline and the query source for metrics. The in-memory
implementation makes the platform runnable end-to-end with no external database (used by the demo and
tests). `PostgresStore` (stub) shows the production path: the same interface, backed by per-tenant
schemas where dbt builds the marts.
"""

from app.store.memory import CanonicalStore

__all__ = ["CanonicalStore"]
