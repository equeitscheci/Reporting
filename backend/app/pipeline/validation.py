"""Declarative data-quality validation (Great-Expectations-style, lightweight).

Rules run over canonical records before they are loaded to the warehouse. Failing rows are routed to
quarantine; passing rows proceed. Rule outcomes are summarized for the freshness/quality dashboard.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from app.canonical.core import CanonicalRecord


@dataclass
class RuleViolation:
    rule: str
    entity: str
    source_id: str
    detail: str


@dataclass
class ValidationReport:
    entity: str
    passed: int = 0
    quarantined: int = 0
    violations: list[RuleViolation] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "entity": self.entity,
            "passed": self.passed,
            "quarantined": self.quarantined,
            "violation_count": len(self.violations),
            "sample_violations": [v.__dict__ for v in self.violations[:10]],
        }


# A rule returns None if OK, or a reason string if violated.
Rule = Callable[[CanonicalRecord], str | None]


def not_null(field_name: str) -> Rule:
    def rule(rec: CanonicalRecord) -> str | None:
        if getattr(rec, field_name, None) in (None, ""):
            return f"{field_name} is null"
        return None

    rule.__name__ = f"not_null[{field_name}]"
    return rule


def non_negative(field_name: str) -> Rule:
    def rule(rec: CanonicalRecord) -> str | None:
        val = getattr(rec, field_name, None)
        if val is not None and val < 0:
            return f"{field_name} is negative ({val})"
        return None

    rule.__name__ = f"non_negative[{field_name}]"
    return rule


def in_range(field_name: str, lo: float, hi: float) -> Rule:
    def rule(rec: CanonicalRecord) -> str | None:
        val = getattr(rec, field_name, None)
        if val is not None and not (lo <= val <= hi):
            return f"{field_name}={val} outside [{lo},{hi}]"
        return None

    rule.__name__ = f"in_range[{field_name}]"
    return rule


def not_future(field_name: str) -> Rule:
    def rule(rec: CanonicalRecord) -> str | None:
        val = getattr(rec, field_name, None)
        if isinstance(val, dt.date) and val > dt.date.today():
            return f"{field_name}={val} is in the future"
        return None

    rule.__name__ = f"not_future[{field_name}]"
    return rule


def default_rules(entity: str) -> list[Rule]:
    """Sensible default rules per canonical entity."""

    common = [not_null("source_id"), not_null("tenant_id")]
    by_entity: dict[str, list[Rule]] = {
        "customer": [not_null("name")],
        "product": [not_null("sku"), non_negative("standard_cost"), non_negative("list_price")],
        "order": [not_null("order_number"), not_null("customer_id"), not_future("order_date")],
        "order_line": [
            not_null("order_number"),
            non_negative("order_qty"),
            non_negative("unit_price"),
            non_negative("unit_cost"),
        ],
        "invoice": [not_null("invoice_number"), non_negative("amount"), non_negative("amount_paid")],
        "inventory_level": [not_null("sku"), non_negative("qty_on_hand")],
    }
    return common + by_entity.get(entity, [])


class Validator:
    def __init__(self, rules_for: Callable[[str], list[Rule]] | None = None) -> None:
        self._rules_for = rules_for or default_rules

    def validate(
        self, entity: str, records: Iterable[CanonicalRecord]
    ) -> tuple[list[CanonicalRecord], list[CanonicalRecord], ValidationReport]:
        """Return (passed, quarantined, report)."""

        rules = self._rules_for(entity)
        passed: list[CanonicalRecord] = []
        quarantined: list[CanonicalRecord] = []
        report = ValidationReport(entity=entity)
        seen_keys: set[str] = set()
        for rec in records:
            reasons: list[str] = []
            # Uniqueness on source_id (primary-key style check).
            if rec.source_id in seen_keys:
                reasons.append("duplicate source_id")
            seen_keys.add(rec.source_id)
            for rule in rules:
                reason = rule(rec)
                if reason:
                    reasons.append(reason)
            if reasons:
                quarantined.append(rec)
                report.quarantined += 1
                for r in reasons:
                    report.violations.append(
                        RuleViolation(rule=r, entity=entity, source_id=rec.source_id, detail=r)
                    )
            else:
                passed.append(rec)
                report.passed += 1
        return passed, quarantined, report
