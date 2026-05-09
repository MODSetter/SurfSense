"""Stop N identical tool calls in a row via interrupt."""

from __future__ import annotations

from app.agents.new_chat.feature_flags import AgentFeatureFlags
from app.agents.new_chat.middleware import DoomLoopMiddleware

from ..shared.flags import enabled


def build_doom_loop_mw(flags: AgentFeatureFlags) -> DoomLoopMiddleware | None:
    return (
        DoomLoopMiddleware(threshold=3) if enabled(flags, "enable_doom_loop") else None
    )
