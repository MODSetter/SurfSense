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

from app.agents.chat.multi_agent_chat.subagents.shared.hitl.questions import (
    STRUCTURED_QUESTION_RESPONSE_ADAPTER,
    StructuredQuestionInterrupt,
    validate_structured_response,
)
from app.utils.perf import get_perf_logger

_perf_log = get_perf_logger()
logger = logging.getLogger(__name__)


@dataclass
class ResumeRoutingPayload:
    """Resolved per-``tool_call_id`` resume slices + the lg-shaped resume map."""

    routed_resume_value: dict[str, Any]
    lg_resume_map: dict[str, Any]
    pending_tool_call_ids: list[str]


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
    from app.agents.chat.multi_agent_chat.main_agent.middleware.checkpointed_subagent_middleware.resume_routing import (
        build_lg_resume_map,
        build_parent_resume_map,
        collect_pending_parent_interrupts,
        collect_pending_tool_calls,
        slice_decisions_by_tool_call,
    )

    parent_state = await agent.aget_state({"configurable": {"thread_id": str(chat_id)}})
    _validate_structured_question_decisions(parent_state, decisions)
    pending = collect_pending_tool_calls(parent_state)
    parent_pending = collect_pending_parent_interrupts(parent_state)
    _perf_log.info(
        "[hitl_route] resume_entry chat_id=%s decisions=%d pending_subagents=%d "
        "pending_parent=%d",
        chat_id,
        len(decisions),
        len(pending),
        len(parent_pending),
    )

    if parent_pending:
        # Parent-side interrupts route by Interrupt.id with no subagent bridge.
        # A mix with subagent pauses can't occur (they fire pre-delegation);
        # fail loud rather than mis-route.
        if pending:
            raise ValueError(
                "Cannot resume: both parent-side and subagent-side interrupts "
                f"are pending (parent={len(parent_pending)}, "
                f"subagent={len(pending)}); mixed HITL routing is unsupported."
            )
        lg_resume_map = build_parent_resume_map(decisions, parent_pending)
        return ResumeRoutingPayload(
            routed_resume_value={},
            lg_resume_map=lg_resume_map,
            pending_tool_call_ids=[],
        )

    routed_resume_value = slice_decisions_by_tool_call(decisions, pending)
    lg_resume_map = build_lg_resume_map(parent_state, routed_resume_value)
    return ResumeRoutingPayload(
        routed_resume_value=routed_resume_value,
        lg_resume_map=lg_resume_map,
        pending_tool_call_ids=[tool_call_id for tool_call_id, _ in pending],
    )


def _validate_structured_question_decisions(
    state: Any,
    decisions: list[dict[str, Any]],
) -> None:
    """Reject stale or approval-shaped answers before resuming a question."""
    interrupts = list(getattr(state, "interrupts", ()) or ())
    if not any(
        isinstance(getattr(item, "value", None), dict)
        and item.value.get("type") == "structured_question"
        for item in interrupts
    ):
        if any(decision.get("type") in {"respond", "cancel"} for decision in decisions):
            raise ValueError("No structured question is pending")
        return

    by_tool_call_id = {
        str(item.value["tool_call_id"]): item
        for item in interrupts
        if isinstance(getattr(item, "value", None), dict)
        if isinstance(item.value.get("tool_call_id"), str)
    }
    by_interrupt_id = {
        str(item.id): item
        for item in interrupts
        if isinstance(getattr(item, "id", None), str)
    }
    positional: list[Any] = []
    for item in interrupts:
        value = getattr(item, "value", None)
        if not isinstance(value, dict):
            continue
        requests = value.get("action_requests")
        count = len(requests) if isinstance(requests, list) and requests else 1
        positional.extend([item] * count)

    for index, decision in enumerate(decisions):
        tool_call_id = decision.get("tool_call_id")
        interrupt_id = decision.get("interrupt_id")
        item = (
            by_tool_call_id.get(str(tool_call_id))
            if tool_call_id
            else by_interrupt_id.get(str(interrupt_id))
            if interrupt_id
            else positional[index]
            if index < len(positional)
            else None
        )
        if item is None:
            if decision.get("type") in {"respond", "cancel"}:
                raise ValueError("Structured-question response has no pending interrupt")
            continue
        value = getattr(item, "value", None)
        is_structured = (
            isinstance(value, dict) and value.get("type") == "structured_question"
        )
        if not is_structured:
            if decision.get("type") in {"respond", "cancel"}:
                raise ValueError("Structured-question response targets an approval")
            continue
        if decision.get("type") not in {"respond", "cancel"}:
            raise ValueError("A structured question requires respond or cancel")
        prompt = StructuredQuestionInterrupt.model_validate(
            {key: field for key, field in value.items() if key != "tool_call_id"}
        )
        response = STRUCTURED_QUESTION_RESPONSE_ADAPTER.validate_python(decision)
        validate_structured_response(prompt, response)
