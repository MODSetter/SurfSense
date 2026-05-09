"""Switch to a fallback model on provider/network errors only."""

from __future__ import annotations

import logging

from app.agents.new_chat.feature_flags import AgentFeatureFlags
from app.agents.new_chat.middleware.scoped_model_fallback import (
    ScopedModelFallbackMiddleware,
)

from ..flags import enabled


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
