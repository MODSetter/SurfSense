"""Stop N identical tool calls in a row via interrupt."""

from __future__ import annotations

from app.agents.shared.feature_flags import AgentFeatureFlags
from app.agents.shared.middleware import DoomLoopMiddleware

from app.agents.multi_agent_chat.middleware.shared.flags import enabled


def build_doom_loop_mw(flags: AgentFeatureFlags) -> DoomLoopMiddleware | None:
    return (
        DoomLoopMiddleware(threshold=3) if enabled(flags, "enable_doom_loop") else None
    )
