"""Provider-compat: append a `_noop` tool when tools=[] but history has tool calls."""

from __future__ import annotations

from app.agents.new_chat.feature_flags import AgentFeatureFlags
from app.agents.new_chat.middleware import NoopInjectionMiddleware

from ..shared.flags import enabled


def build_noop_injection_mw(flags: AgentFeatureFlags) -> NoopInjectionMiddleware | None:
    return NoopInjectionMiddleware() if enabled(flags, "enable_compaction_v2") else None
