"""Industry-specific canonical extensions (vertical packs).

These are additive entities, not forks of core. A tenant's enabled `industry_packs` decide which of
these participate in mapping, marts, metrics, and dashboards.
"""

from __future__ import annotations

import datetime as dt

from app.canonical.core import CanonicalRecord


# ----------------------------------------------------------------------------- Manufacturing
class BOM(CanonicalRecord):
    bom_id: str
    sku: str  # parent assembly
    revision: str | None = None


class BOMComponent(CanonicalRecord):
    bom_id: str
    component_sku: str
    quantity_per: float = 1.0
    scrap_pct: float = 0.0


class Routing(CanonicalRecord):
    routing_id: str
    sku: str


class RoutingOperation(CanonicalRecord):
    routing_id: str
    operation_seq: int
    work_center: str | None = None
    setup_hours: float = 0.0
    run_hours_per_unit: float = 0.0


class ProductionRun(CanonicalRecord):
    run_id: str
    job_number: str | None = None
    sku: str
    planned_qty: float = 0.0
    completed_qty: float = 0.0
    scrapped_qty: float = 0.0
    start_date: dt.date | None = None
    end_date: dt.date | None = None


class JobCost(CanonicalRecord):
    """Actual costs booked to a job/production run (material, labor, burden)."""

    job_number: str
    cost_code: str | None = None
    cost_type: str | None = None  # material|labor|burden|subcontract
    amount: float = 0.0
    posting_date: dt.date | None = None


# ------------------------------------------------------------------------------- Construction
class Project(CanonicalRecord):
    project_id: str
    customer_id: str | None = None
    name: str | None = None
    status: str | None = None
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    contract_value: float | None = None


class CostCode(CanonicalRecord):
    cost_code: str
    description: str | None = None
    division: str | None = None


class Budget(CanonicalRecord):
    budget_id: str
    project_id: str


class BudgetLine(CanonicalRecord):
    budget_id: str
    cost_code: str
    budget_amount: float = 0.0


class Schedule(CanonicalRecord):
    schedule_id: str
    project_id: str


class ScheduleTask(CanonicalRecord):
    schedule_id: str
    task_id: str
    name: str | None = None
    planned_start: dt.date | None = None
    planned_finish: dt.date | None = None
    actual_start: dt.date | None = None
    actual_finish: dt.date | None = None
    pct_complete: float = 0.0


# ------------------------------------------------------------------------------- Field Service
class ServiceTicket(CanonicalRecord):
    ticket_id: str
    customer_id: str | None = None
    priority: str | None = None
    status: str | None = None
    opened_at: dt.datetime | None = None
    resolved_at: dt.datetime | None = None
    sla_due_at: dt.datetime | None = None
    technician_id: str | None = None


class Dispatch(CanonicalRecord):
    dispatch_id: str
    ticket_id: str
    technician_id: str
    scheduled_at: dt.datetime | None = None
    arrived_at: dt.datetime | None = None
    completed_at: dt.datetime | None = None


class Technician(CanonicalRecord):
    technician_id: str
    name: str | None = None
    region: str | None = None
    available_hours: float | None = None


class SLA(CanonicalRecord):
    sla_id: str
    name: str | None = None
    priority: str | None = None
    response_hours: float | None = None
    resolution_hours: float | None = None
