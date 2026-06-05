"""Provider-compat: append a `_noop` tool when tools=[] but history has tool calls."""

from __future__ import annotations

from app.agents.multi_agent_chat.shared.middleware.flags import enabled
from app.agents.shared.feature_flags import AgentFeatureFlags

from .middleware import NoopInjectionMiddleware


def build_noop_injection_mw(flags: AgentFeatureFlags) -> NoopInjectionMiddleware | None:
    return NoopInjectionMiddleware() if enabled(flags, "enable_compaction_v2") else None
