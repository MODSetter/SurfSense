"""Stop N identical tool calls in a row via interrupt."""

from __future__ import annotations

from app.agents.chat.multi_agent_chat.shared.feature_flags import AgentFeatureFlags
from app.agents.chat.multi_agent_chat.shared.middleware.flags import enabled

from .middleware import DoomLoopMiddleware


def build_doom_loop_mw(flags: AgentFeatureFlags) -> DoomLoopMiddleware | None:
    return (
        DoomLoopMiddleware(threshold=3) if enabled(flags, "enable_doom_loop") else None
    )
