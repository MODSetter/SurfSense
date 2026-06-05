"""Switch to a fallback model on provider/network errors only."""

from __future__ import annotations

import logging

from app.agents.multi_agent_chat.shared.feature_flags import AgentFeatureFlags

from ..flags import enabled
from .scoped_model_fallback import (
    ScopedModelFallbackMiddleware,
)


def build_fallback_mw(
    flags: AgentFeatureFlags,
) -> ScopedModelFallbackMiddleware | None:
    if not enabled(flags, "enable_model_fallback"):
        return None
    try:
        return ScopedModelFallbackMiddleware(
            "openai:gpt-4o-mini",
            "anthropic:claude-3-5-haiku-20241022",
        )
    except Exception:
        logging.warning("ScopedModelFallbackMiddleware init failed; skipping.")
        return None
