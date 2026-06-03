"""Mapping engine + transforms + validation."""

from __future__ import annotations

from app.connectors.sdk import Record
from app.mapping.engine import MappingEngine
from app.mapping.spec import MappingSpec
from app.mapping.transforms import apply_transform, safe_eval
from app.pipeline.validation import Validator

SPEC_YAML = """
source_system: testerp
entities:
  - source_stream: customers
    target_entity: customer
    source_id: CustNum
    fields:
      name: CustName
      region: Region
      credit_limit: { transform: { op: cast, type: float, from: Limit } }
  - source_stream: order_lines
    target_entity: order_line
    source_id: [OrderNum, LineNum]
    fields:
      order_number: { transform: { op: cast, type: str, from: OrderNum } }
      line_number: { transform: { op: cast, type: int, from: LineNum } }
      sku: Part
      order_qty: { transform: { op: cast, type: float, from: Qty } }
      unit_price: { transform: { op: cast, type: float, from: Price } }
      unit_cost: { transform: { op: cast, type: float, from: Cost } }
"""


def test_safe_eval_blocks_dangerous():
    assert safe_eval("a + b", {"a": 1, "b": 2}) == 3
    assert safe_eval("coalesce(a, b)", {"a": None, "b": 5}) == 5
    try:
        safe_eval("__import__('os')", {})
        assert False
    except ValueError:
        pass


def test_transforms():
    assert apply_transform({"op": "cast", "type": "float", "from": "x"}, {"x": "1,200.50"}) == 1200.50
    assert apply_transform({"op": "concat", "fields": ["a", "b"], "sep": "-"}, {"a": "1", "b": "2"}) == "1-2"
    assert apply_transform({"op": "lookup", "from": "k", "table": {"A": "Active"}}, {"k": "A"}) == "Active"


def test_mapping_engine_produces_canonical():
    spec = MappingSpec.from_yaml(SPEC_YAML)
    engine = MappingEngine(spec, tenant_id="t1")
    recs = [
        Record(stream="customers", data={"CustNum": "C1", "CustName": "Acme", "Region": "West", "Limit": "5000"}),
    ]
    result = engine.map_stream("customers", recs)
    assert result.ok == 1
    cust = result.records[0]
    assert cust.name == "Acme"
    assert cust.credit_limit == 5000.0
    assert cust.tenant_id == "t1"
    assert cust.source_system == "testerp"
    assert cust.source_id == "C1"
    assert cust.row_hash  # lineage populated


def test_composite_source_id():
    spec = MappingSpec.from_yaml(SPEC_YAML)
    engine = MappingEngine(spec, tenant_id="t1")
    rec = Record(stream="order_lines",
                 data={"OrderNum": 10, "LineNum": 2, "Part": "P1", "Qty": "5", "Price": "3", "Cost": "1"})
    res = engine.map_stream("order_lines", [rec])
    assert res.records[0].source_id == "10|2"
    assert res.records[0].extended_revenue == 15.0


def test_validation_quarantines_bad_rows():
    spec = MappingSpec.from_yaml(SPEC_YAML)
    engine = MappingEngine(spec, tenant_id="t1")
    recs = [
        Record(stream="order_lines", data={"OrderNum": 1, "LineNum": 1, "Part": "P", "Qty": "5", "Price": "2", "Cost": "1"}),
        Record(stream="order_lines", data={"OrderNum": 2, "LineNum": 1, "Part": "P", "Qty": "-5", "Price": "2", "Cost": "1"}),
    ]
    res = engine.map_stream("order_lines", recs)
    passed, quarantined, report = Validator().validate("order_line", res.records)
    assert report.passed == 1
    assert report.quarantined == 1
