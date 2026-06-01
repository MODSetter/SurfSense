"""Pure JSON filter grammar: ``matches(filter_expr, payload) -> bool``.

The ``event`` trigger uses it to decide whether an event fires the automation.
"""

from __future__ import annotations

import operator
from collections.abc import Callable
from typing import Any


class FilterError(ValueError):
    """Unknown operator in a filter. Raised (not silently false) so a bad filter
    fails at authoring time instead of quietly disabling the trigger."""


# Scalar comparison operators: (actual, operand) -> bool.
_COMPARATORS: dict[str, Callable[[Any, Any], bool]] = {
    "$eq": operator.eq,
    "$ne": operator.ne,
    "$gt": operator.gt,
    "$gte": operator.ge,
    "$lt": operator.lt,
    "$lte": operator.le,
    "$in": lambda actual, operand: actual in operand,
    "$nin": lambda actual, operand: actual not in operand,
}

# Sentinel for "the payload has no such field" — distinct from a present None.
_MISSING = object()


def matches(filter_expr: dict[str, Any], payload: dict[str, Any]) -> bool:
    """Return ``True`` when ``payload`` satisfies every constraint in ``filter_expr``.

    An empty filter expresses "no constraints" and matches every payload.
    Sibling keys (fields and logical operators alike) are ANDed together.
    """
    for key, value in filter_expr.items():
        if key == "$and":
            if not all(matches(sub, payload) for sub in value):
                return False
        elif key == "$or":
            if not any(matches(sub, payload) for sub in value):
                return False
        elif key == "$not":
            if matches(value, payload):
                return False
        elif key.startswith("$"):
            raise FilterError(f"unknown logical operator: {key}")
        elif not _match_condition(value, payload.get(key, _MISSING)):
            return False
    return True


def _match_condition(condition: Any, actual: Any) -> bool:
    """Match one field's ``actual`` value against its ``condition``.

    A dict condition is an operator object (``{"$gt": 10}``); every operator in
    it must hold. Any other value is an implicit equality check. A field absent
    from the payload (``actual is _MISSING``) fails every constraint.
    """
    if actual is _MISSING:
        return False
    if isinstance(condition, dict):
        return all(
            _apply_operator(op, operand, actual) for op, operand in condition.items()
        )
    return actual == condition


def _apply_operator(op: str, operand: Any, actual: Any) -> bool:
    comparator = _COMPARATORS.get(op)
    if comparator is not None:
        return comparator(actual, operand)
    raise FilterError(f"unknown operator: {op}")
