"""End an agent run once its settled model cost crosses a ceiling.

``ModelCallLimitMiddleware`` caps how many model calls a run may make and
``ToolCallLimitMiddleware`` caps tool calls, but neither bounds spend. A run
can sit well inside the 80-call limit and still settle at $21 by stuffing a
400k-token context into each call — which is what the most expensive turns in
production actually did. The pre-flight reservation does not help either: it
is a hold, and finalize settles at LiteLLM's real cost regardless of it.

This middleware closes that gap by reading the live
:class:`~app.services.token_tracking_service.TurnTokenAccumulator` — the same
object the premium wallet settles against — after every model call, and
ending the run when accumulated cost exceeds the ceiling.

The accumulator is a ContextVar scoped to the whole user turn, and subagents
run inside that context, so the single instance shared through
:class:`ResilienceMiddlewares` bounds the *turn* (main agent plus every
subagent it spawns) rather than each graph in isolation. That is deliberate:
the runaway turns observed in production fanned out across subagents, so a
per-graph ceiling would have missed them.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ContextT,
    ResponseT,
)
from langgraph.runtime import Runtime

from app.config import config
from app.services.token_tracking_service import get_current_accumulator

logger = logging.getLogger(__name__)


class RunCostLimitMiddleware(
    AgentMiddleware[AgentState[ResponseT], ContextT, ResponseT]
):
    """Jump to ``end`` once the turn's accumulated model cost hits the ceiling.

    Args:
        max_cost_micros: Ceiling in micro-USD (1_000_000 == $1.00). Must be
            positive; callers disable the middleware by not building it.
    """

    def __init__(self, *, max_cost_micros: int) -> None:
        super().__init__()
        if max_cost_micros <= 0:
            raise ValueError("RunCostLimitMiddleware max_cost_micros must be > 0")
        self._max_cost_micros = max_cost_micros
        self.tools = []

    def after_model(  # type: ignore[override]
        self,
        state: AgentState[ResponseT],
        runtime: Runtime[ContextT],
    ) -> dict[str, Any] | None:
        accumulator = get_current_accumulator()
        # No accumulator means nothing is metering this run (unit tests, or a
        # path that never called start_turn/scoped_turn). Fail open: this is a
        # cost guard, not an authorization check, and the wallet still settles.
        if accumulator is None:
            return None

        # The credit reservation publishes the plan's ceiling onto the turn; a
        # turn that never reserved (free models, so no allowance at stake)
        # leaves it unset and takes the configured default. The comparison
        # lives on the accumulator because the background artifact pipelines
        # need the same check without an agent to hang middleware off.
        if not accumulator.run_cost_ceiling_reached(self._max_cost_micros):
            return None

        ceiling = accumulator.run_cost_ceiling_micros(self._max_cost_micros)
        spent_micros = accumulator.total_cost_micros

        logger.warning(
            "Run cost limit hit: turn settled at %d micros across %d model "
            "call(s), ceiling %d micros. Ending run.",
            spent_micros,
            len(accumulator.calls),
            ceiling,
        )
        # Ending the graph is invisible to the user — they get whatever partial
        # answer already streamed and no reason for the stop. The flag rides
        # out on the turn's ``data-token-usage`` frame, the same channel
        # ``truncated`` uses, so the frontend can say which limit was hit.
        accumulator.cost_limited = True
        return {"jump_to": "end"}

    async def aafter_model(  # type: ignore[override]
        self,
        state: AgentState[ResponseT],
        runtime: Runtime[ContextT],
    ) -> dict[str, Any] | None:
        return self.after_model(state, runtime)


def build_run_cost_limit_mw() -> RunCostLimitMiddleware | None:
    """Build from ``AGENT_MAX_RUN_COST_MICROS``; ``None`` when set to 0."""
    ceiling = config.AGENT_MAX_RUN_COST_MICROS
    if ceiling <= 0:
        return None
    return RunCostLimitMiddleware(max_cost_micros=ceiling)


__all__ = ["RunCostLimitMiddleware", "build_run_cost_limit_mw"]
