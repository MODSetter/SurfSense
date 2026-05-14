"""Build the ``interrupt_on`` map fed into ``HumanInTheLoopMiddleware``.

The map keys are tool names whose execution must be intercepted before
the call runs. Self-gated rows are intentionally excluded: their bodies
already pause via :func:`request_approval`, and intercepting them too
would double-prompt the user.
"""

from __future__ import annotations

from app.agents.multi_agent_chat.subagents.shared.tool_kinds import ToolsPermissions


def middleware_gated_interrupt_on(bucket: ToolsPermissions) -> dict[str, bool]:
    """``interrupt_on`` map for ``ask`` rows whose bodies don't self-gate."""
    return {
        r["name"]: True
        for r in bucket["ask"]
        if r.get("name") and r.get("kind") == "middleware_gated"
    }


__all__ = ["middleware_gated_interrupt_on"]
