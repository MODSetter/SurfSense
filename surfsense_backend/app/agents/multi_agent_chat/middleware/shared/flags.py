"""Single source of truth for the feature-flag predicate."""

from __future__ import annotations

from app.agents.new_chat.feature_flags import AgentFeatureFlags


def enabled(flags: AgentFeatureFlags, attr: str) -> bool:
    """``flags.<attr>`` is on AND the new-agent-stack kill switch is off."""
    return getattr(flags, attr) and not flags.disable_new_agent_stack
