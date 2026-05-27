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
