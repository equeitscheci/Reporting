"""Transform library for the mapping engine.

Transforms are pure functions selected by `op`. Expressions use a sandboxed evaluator (no builtins,
no attribute access) so tenant-authored config cannot execute arbitrary code.
"""

from __future__ import annotations

import ast
import datetime as dt
import operator
from typing import Any, Callable

# ----------------------------------------------------------------- safe expression evaluator
_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_ALLOWED_CMP = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}
_ALLOWED_FUNCS: dict[str, Callable] = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "len": len,
    "lower": lambda s: str(s).lower(),
    "upper": lambda s: str(s).upper(),
    "strip": lambda s: str(s).strip(),
    "float": float,
    "int": int,
    "str": str,
    "coalesce": lambda *a: next((x for x in a if x not in (None, "")), None),
}


def safe_eval(expr: str, row: dict[str, Any]) -> Any:
    """Evaluate a restricted expression against `row` (exposed as variables)."""

    tree = ast.parse(expr, mode="eval")
    return _eval(tree.body, row)


def _eval(node: ast.AST, row: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return row.get(node.id)
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        return _ALLOWED_BINOPS[type(node.op)](_eval(node.left, row), _eval(node.right, row))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval(node.operand, row)
    if isinstance(node, ast.BoolOp):
        vals = [_eval(v, row) for v in node.values]
        return all(vals) if isinstance(node.op, ast.And) else any(vals)
    if isinstance(node, ast.Compare) and type(node.ops[0]) in _ALLOWED_CMP:
        return _ALLOWED_CMP[type(node.ops[0])](
            _eval(node.left, row), _eval(node.comparators[0], row)
        )
    if isinstance(node, ast.IfExp):
        return _eval(node.body, row) if _eval(node.test, row) else _eval(node.orelse, row)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        fn = _ALLOWED_FUNCS.get(node.func.id)
        if fn is None:
            raise ValueError(f"Function not allowed in expression: {node.func.id}")
        return fn(*[_eval(a, row) for a in node.args])
    raise ValueError(f"Unsupported expression element: {ast.dump(node)}")


# --------------------------------------------------------------------------------- casts
def _to_float(v: Any) -> float | None:
    if v in (None, ""):
        return None
    return float(str(v).replace(",", "").replace("$", ""))


def _to_int(v: Any) -> int | None:
    f = _to_float(v)
    return int(f) if f is not None else None


def _to_date(v: Any, fmt: str | None = None) -> dt.date | None:
    if v in (None, ""):
        return None
    if isinstance(v, dt.date):
        return v
    s = str(v)
    if fmt:
        return dt.datetime.strptime(s, fmt).date()
    return dt.date.fromisoformat(s[:10])


def _to_datetime(v: Any, fmt: str | None = None) -> dt.datetime | None:
    if v in (None, ""):
        return None
    if isinstance(v, dt.datetime):
        return v
    s = str(v)
    if fmt:
        return dt.datetime.strptime(s, fmt)
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


CASTS = {"float": _to_float, "int": _to_int, "date": _to_date, "datetime": _to_datetime, "str": str}


def apply_transform(spec: dict[str, Any], row: dict[str, Any]) -> Any:
    """Apply one transform op to a source row, returning the canonical value."""

    op = spec.get("op", "direct")

    if op == "direct":
        return row.get(spec["from"])

    if op == "const":
        return spec.get("value")

    if op == "cast":
        raw = row.get(spec["from"]) if "from" in spec else None
        caster = CASTS[spec["type"]]
        if spec["type"] in ("date", "datetime") and "format" in spec:
            return caster(raw, spec["format"])
        return caster(raw)

    if op == "concat":
        sep = spec.get("sep", " ")
        parts = [str(row.get(f, "")) for f in spec["fields"]]
        return sep.join(p for p in parts if p)

    if op == "lookup":
        table = spec.get("table", {})
        key = row.get(spec["from"])
        return table.get(str(key), spec.get("default"))

    if op == "expr":
        return safe_eval(spec["expr"], row)

    if op == "coalesce":
        for f in spec["fields"]:
            val = row.get(f)
            if val not in (None, ""):
                return val
        return spec.get("default")

    raise ValueError(f"Unknown transform op: {op}")
