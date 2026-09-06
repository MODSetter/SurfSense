"""Construct each resilience middleware once; same instances flow into every consumer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
)

from app.agents.chat.multi_agent_chat.shared.feature_flags import AgentFeatureFlags
from app.agents.chat.shared.middleware import RetryAfterMiddleware

from .fallback import build_fallback_mw
from .model_call_limit import build_model_call_limit_mw
from .retry import build_retry_mw
from .run_cost_limit import RunCostLimitMiddleware, build_run_cost_limit_mw
from .scoped_model_fallback import (
    ScopedModelFallbackMiddleware,
)
from .tool_call_limit import build_tool_call_limit_mw


@dataclass(frozen=True)
class ResilienceMiddlewares:
    """The five resilience middleware instances, any of which may be ``None`` when disabled by flags or config."""

    retry: RetryAfterMiddleware | None
    fallback: ScopedModelFallbackMiddleware | None
    model_call_limit: ModelCallLimitMiddleware | None
    tool_call_limit: ToolCallLimitMiddleware | None
    # Bounds settled spend, which the two call-count limits above do not.
    # Shared as one instance so it bounds the whole turn, subagents included.
    run_cost_limit: RunCostLimitMiddleware | None

    def as_list(self) -> list[Any]:
        return [
            m
            for m in (
                self.retry,
                self.fallback,
                self.model_call_limit,
                self.tool_call_limit,
                self.run_cost_limit,
            )
            if m is not None
        ]


def build_resilience_middlewares(flags: AgentFeatureFlags) -> ResilienceMiddlewares:
    return ResilienceMiddlewares(
        retry=build_retry_mw(flags),
        fallback=build_fallback_mw(flags),
        model_call_limit=build_model_call_limit_mw(flags),
        tool_call_limit=build_tool_call_limit_mw(flags),
        run_cost_limit=build_run_cost_limit_mw(),
    )
