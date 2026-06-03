"""Canonical (ERP-agnostic) data model + industry extension packs.

Everything downstream of the mapping engine targets these entities, never a vendor schema.
"""

from app.canonical.core import (
    CanonicalRecord,
    Customer,
    GLAccount,
    GLEntry,
    Invoice,
    InvoiceLine,
    InventoryLevel,
    Job,
    Order,
    OrderLine,
    Payment,
    Product,
    Vendor,
    WorkOrder,
)
from app.canonical.registry import ENTITIES, get_entity

__all__ = [
    "CanonicalRecord",
    "Customer",
    "Vendor",
    "Product",
    "InventoryLevel",
    "Order",
    "OrderLine",
    "Invoice",
    "InvoiceLine",
    "Payment",
    "GLAccount",
    "GLEntry",
    "Job",
    "WorkOrder",
    "ENTITIES",
    "get_entity",
]
