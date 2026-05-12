"""Construct each resilience middleware once; same instances flow into every consumer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
)

from app.agents.new_chat.feature_flags import AgentFeatureFlags
from app.agents.new_chat.middleware import RetryAfterMiddleware
from app.agents.new_chat.middleware.scoped_model_fallback import (
    ScopedModelFallbackMiddleware,
)

from .fallback import build_fallback_mw
from .model_call_limit import build_model_call_limit_mw
from .retry import build_retry_mw
from .tool_call_limit import build_tool_call_limit_mw


@dataclass(frozen=True)
class ResilienceBundle:
    retry: RetryAfterMiddleware | None
    fallback: ScopedModelFallbackMiddleware | None
    model_call_limit: ModelCallLimitMiddleware | None
    tool_call_limit: ToolCallLimitMiddleware | None

    def as_list(self) -> list[Any]:
        return [
            m
            for m in (
                self.retry,
                self.fallback,
                self.model_call_limit,
                self.tool_call_limit,
            )
            if m is not None
        ]


def build_resilience_bundle(flags: AgentFeatureFlags) -> ResilienceBundle:
    return ResilienceBundle(
        retry=build_retry_mw(flags),
        fallback=build_fallback_mw(flags),
        model_call_limit=build_model_call_limit_mw(flags),
        tool_call_limit=build_tool_call_limit_mw(flags),
    )
