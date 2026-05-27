"""Sandboxed template engine for automation definitions."""

from __future__ import annotations

from .context import build_run_context
from .render import evaluate_predicate, render_template

__all__ = [
    "build_run_context",
    "evaluate_predicate",
    "render_template",
]
