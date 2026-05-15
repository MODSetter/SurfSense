"""Shared middleware stack threaded into every subagent.

Mirrors ``middleware/stack.py`` (the orchestrator's middleware stack) but
exposes its contents as a dict keyed by purpose so specialists can pick
the entries they need and decide ordering. The default consumer
(``pack_subagent``) prepends every non-``None`` value in insertion order.

Registry subagents never touch the SurfSense filesystem — that capability
belongs to ``knowledge_base`` — so no FS middleware is exposed here.
"""

from __future__ import annotations

from typing import Any

from ..shared.resilience import ResilienceMiddlewares
from ..shared.todos import build_todos_mw


def build_subagent_middleware_stack(
    *,
    resilience: ResilienceMiddlewares,
) -> dict[str, Any]:
    return {
        "todos": build_todos_mw(),
        "retry": resilience.retry,
        "fallback": resilience.fallback,
        "model_call_limit": resilience.model_call_limit,
        "tool_call_limit": resilience.tool_call_limit,
    }
