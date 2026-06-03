"""Registry mapping canonical entity names → model classes, grouped by industry pack.

The mapping engine and pipeline resolve target entities by name (as written in mapping YAML).
"""

from __future__ import annotations

from app.canonical import core, extensions
from app.canonical.core import CanonicalRecord

CORE_ENTITIES: dict[str, type[CanonicalRecord]] = {
    "customer": core.Customer,
    "vendor": core.Vendor,
    "product": core.Product,
    "inventory_level": core.InventoryLevel,
    "order": core.Order,
    "order_line": core.OrderLine,
    "invoice": core.Invoice,
    "invoice_line": core.InvoiceLine,
    "payment": core.Payment,
    "gl_account": core.GLAccount,
    "gl_entry": core.GLEntry,
    "job": core.Job,
    "work_order": core.WorkOrder,
}

INDUSTRY_PACKS: dict[str, dict[str, type[CanonicalRecord]]] = {
    "manufacturing": {
        "bom": extensions.BOM,
        "bom_component": extensions.BOMComponent,
        "routing": extensions.Routing,
        "routing_operation": extensions.RoutingOperation,
        "production_run": extensions.ProductionRun,
        "job_cost": extensions.JobCost,
    },
    "construction": {
        "project": extensions.Project,
        "cost_code": extensions.CostCode,
        "budget": extensions.Budget,
        "budget_line": extensions.BudgetLine,
        "schedule": extensions.Schedule,
        "schedule_task": extensions.ScheduleTask,
    },
    "field_service": {
        "service_ticket": extensions.ServiceTicket,
        "dispatch": extensions.Dispatch,
        "technician": extensions.Technician,
        "sla": extensions.SLA,
    },
    # Distribution & Finance reuse core entities; their specifics live in the marts/metrics layer.
    "distribution": {},
    "finance": {},
}

# Flattened view of every known entity.
ENTITIES: dict[str, type[CanonicalRecord]] = dict(CORE_ENTITIES)
for _pack in INDUSTRY_PACKS.values():
    ENTITIES.update(_pack)


def get_entity(name: str) -> type[CanonicalRecord]:
    if name not in ENTITIES:
        raise KeyError(f"Unknown canonical entity '{name}'. Known: {sorted(ENTITIES)}")
    return ENTITIES[name]


def entities_for_packs(packs: list[str]) -> dict[str, type[CanonicalRecord]]:
    """Core entities + entities contributed by the tenant's enabled industry packs."""

    out = dict(CORE_ENTITIES)
    for p in packs:
        out.update(INDUSTRY_PACKS.get(p, {}))
    return out
