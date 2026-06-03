"""Core canonical entities shared by every industry vertical.

Field names are deliberately ERP-neutral. Each entity carries lineage metadata so any canonical row
can be traced back to the exact source record it came from.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CanonicalRecord(BaseModel):
    """Base for all canonical entities. Holds multi-tenant + lineage metadata."""

    model_config = ConfigDict(extra="allow")  # vertical extensions add fields

    tenant_id: str
    source_system: str
    source_id: str  # natural/primary key in the source
    ingested_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    row_hash: str | None = None

    def compute_hash(self) -> str:
        """Stable content hash (excludes volatile lineage fields) for change detection/upserts."""

        payload = self.model_dump(exclude={"ingested_at", "row_hash"}, mode="json")
        blob = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode()).hexdigest()

    def finalize(self) -> "CanonicalRecord":
        self.row_hash = self.compute_hash()
        return self


class Customer(CanonicalRecord):
    name: str
    region: str | None = None
    segment: str | None = None
    status: str | None = None
    credit_limit: float | None = None


class Vendor(CanonicalRecord):
    name: str
    region: str | None = None
    status: str | None = None


class Product(CanonicalRecord):
    sku: str
    description: str | None = None
    product_group: str | None = None
    standard_cost: float | None = None
    list_price: float | None = None
    uom: str | None = None


class InventoryLevel(CanonicalRecord):
    sku: str
    location: str | None = None
    snapshot_date: dt.date
    qty_on_hand: float = 0.0
    unit_cost: float | None = None
    # Distribution metrics are derived in marts but can be carried if the source provides them.
    qty_committed: float | None = None
    qty_on_order: float | None = None


class Order(CanonicalRecord):
    order_number: str
    customer_id: str
    order_date: dt.date | None = None
    status: str | None = None
    currency: str = "USD"


class OrderLine(CanonicalRecord):
    order_number: str
    line_number: int
    sku: str
    order_qty: float = 0.0
    ship_qty: float | None = None
    unit_price: float = 0.0
    unit_cost: float = 0.0

    @property
    def extended_revenue(self) -> float:
        return round(self.order_qty * self.unit_price, 2)

    @property
    def extended_cost(self) -> float:
        return round(self.order_qty * self.unit_cost, 2)


class Invoice(CanonicalRecord):
    invoice_number: str
    order_number: str | None = None
    customer_id: str
    invoice_date: dt.date | None = None
    due_date: dt.date | None = None
    amount: float = 0.0
    amount_paid: float = 0.0

    @property
    def open_balance(self) -> float:
        return round(self.amount - self.amount_paid, 2)


class InvoiceLine(CanonicalRecord):
    invoice_number: str
    line_number: int
    sku: str | None = None
    quantity: float = 0.0
    unit_price: float = 0.0
    amount: float = 0.0


class Payment(CanonicalRecord):
    payment_id: str
    invoice_number: str | None = None
    customer_id: str | None = None
    payment_date: dt.date | None = None
    amount: float = 0.0
    method: str | None = None


class GLAccount(CanonicalRecord):
    account_code: str
    name: str
    account_type: str | None = None  # asset|liability|equity|revenue|expense
    parent_code: str | None = None


class GLEntry(CanonicalRecord):
    entry_id: str
    account_code: str
    posting_date: dt.date | None = None
    debit: float = 0.0
    credit: float = 0.0
    job_id: str | None = None
    memo: str | None = None


class Job(CanonicalRecord):
    """Job/Project — shared by construction and manufacturing."""

    job_number: str
    customer_id: str | None = None
    description: str | None = None
    status: str | None = None
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    budget_amount: float | None = None


class WorkOrder(CanonicalRecord):
    """Work order / service ticket base — extended by manufacturing & field service packs."""

    work_order_number: str
    job_number: str | None = None
    customer_id: str | None = None
    status: str | None = None
    opened_date: dt.date | None = None
    closed_date: dt.date | None = None
    assigned_to: str | None = None
