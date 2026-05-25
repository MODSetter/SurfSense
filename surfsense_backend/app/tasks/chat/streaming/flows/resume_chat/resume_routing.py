"""Route a flat ``decisions`` list back to the right paused subagent.

Each pending interrupt is stamped with its originating ``tool_call_id`` (see
``checkpointed_subagent_middleware.propagation``) so the resume slicer can
re-target each ``HumanReview`` decision at the right ``tool_call_id``.

LangGraph rejects scalar ``Command(resume=...)`` when multiple interrupts are
pending (parallel HITL); the mapped form works for the single-pause case too,
so we always use it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.utils.perf import get_perf_logger

_perf_log = get_perf_logger()
logger = logging.getLogger(__name__)


@dataclass
class ResumeRoutingPayload:
    """Resolved per-``tool_call_id`` resume slices + the lg-shaped resume map."""

    routed_resume_value: dict[str, Any]
    lg_resume_map: dict[str, Any]


async def build_resume_routing(
    agent: Any,
    *,
    chat_id: int,
    decisions: list[dict],
) -> ResumeRoutingPayload:
    """Read parent_state, collect pending tool-calls, slice decisions, build map.

    The middleware reads its per-``tool_call_id`` resume slice from the
    ``surfsense_resume_value`` configurable; parallel siblings each pop their
    own entry so they never race.
    """
    from app.agents.multi_agent_chat.middleware.main_agent.checkpointed_subagent_middleware.resume_routing import (
        build_lg_resume_map,
        collect_pending_tool_calls,
        slice_decisions_by_tool_call,
    )

    parent_state = await agent.aget_state(
        {"configurable": {"thread_id": str(chat_id)}}
    )
    pending = collect_pending_tool_calls(parent_state)
    _perf_log.info(
        "[hitl_route] resume_entry chat_id=%s decisions=%d pending_subagents=%d",
        chat_id,
        len(decisions),
        len(pending),
    )
    routed_resume_value = slice_decisions_by_tool_call(decisions, pending)
    lg_resume_map = build_lg_resume_map(parent_state, routed_resume_value)
    return ResumeRoutingPayload(
        routed_resume_value=routed_resume_value,
        lg_resume_map=lg_resume_map,
    )
