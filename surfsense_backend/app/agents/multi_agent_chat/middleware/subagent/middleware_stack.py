"""Shared middleware stack threaded into every subagent.

Mirrors ``middleware/stack.py`` (the orchestrator's middleware stack) but
exposes its contents as a dict keyed by purpose so specialists can pick
the entries they need and decide ordering. The default consumer
(:func:`pack_subagent`) prepends every non-``None`` value in insertion
order, so ``None`` slots are silently skipped.

Registry subagents never touch the SurfSense filesystem — that capability
belongs to ``knowledge_base`` — so no FS middleware is exposed here.
"""

from __future__ import annotations

from typing import Any

from app.agents.new_chat.feature_flags import AgentFeatureFlags

from ..shared.permissions import build_permission_mw
from ..shared.resilience import ResilienceMiddlewares
from ..shared.todos import build_todos_mw


def build_subagent_middleware_stack(
    *,
    resilience: ResilienceMiddlewares,
    flags: AgentFeatureFlags | None = None,
) -> dict[str, Any]:
    """Assemble the dict of middlewares prepended to every subagent's stack.

    Args:
        resilience: Pre-built retry / fallback / call-limit middlewares
            (shared with the orchestrator stack to keep behaviour symmetric).
        flags: Feature flags driving optional layers. ``None`` disables the
            permission layer (used in tests that only need todos+resilience).

    Returns:
        Insertion-ordered dict; ``None`` values are tolerated and dropped by
        the consumer so callers can flip slots on/off without reshaping.
    """
    permission = build_permission_mw(flags=flags) if flags is not None else None
    return {
        "todos": build_todos_mw(),
        "permission": permission,
        "retry": resilience.retry,
        "fallback": resilience.fallback,
        "model_call_limit": resilience.model_call_limit,
        "tool_call_limit": resilience.tool_call_limit,
    }
