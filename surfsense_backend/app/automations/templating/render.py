"""Render templates and evaluate predicates against the sandboxed environment."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .environment import ENV


def render_template(template: str, context: Mapping[str, Any]) -> str:
    """Render ``template`` with ``context``."""
    return ENV.from_string(template).render(**context)


def evaluate_predicate(expression: str, context: Mapping[str, Any]) -> bool:
    """Evaluate a Jinja expression (not a template body) and coerce to bool."""
    return bool(ENV.compile_expression(expression)(**context))


def render_value(value: Any, context: Mapping[str, Any]) -> Any:
    """Recursively render every string in a JSON-like value structure."""
    if isinstance(value, str):
        return render_template(value, context)
    if isinstance(value, dict):
        return {k: render_value(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [render_value(v, context) for v in value]
    return value
