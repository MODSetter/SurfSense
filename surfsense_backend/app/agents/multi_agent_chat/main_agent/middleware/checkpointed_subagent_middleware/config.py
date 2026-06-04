"""RunnableConfig wiring for nested subagent invocations.

Forwards the parent's ``runtime.config`` (thread_id, …) into the subagent and
exposes the side-channel ``stream_resume_chat`` uses to ferry resume payloads.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain.tools import ToolRuntime

from .constants import DEFAULT_SUBAGENT_RECURSION_LIMIT

logger = logging.getLogger(__name__)

# langgraph stores the parent task's scratchpad under this configurable key;
# subagents inherit the chain via ``parent_scratchpad`` fallback.
_LANGGRAPH_SCRATCHPAD_KEY = "__pregel_scratchpad"


def subagent_invoke_config(runtime: ToolRuntime) -> dict[str, Any]:
    """RunnableConfig for the nested invoke; raises ``recursion_limit`` and isolates ``thread_id``.

    Each parallel subagent invocation lands in its own checkpoint slot keyed
    by an extended ``thread_id`` of the form ``{parent_thread}::task:{tool_call_id}``.
    The same call across the resume cycle keeps reading from the same snapshot
    (``tool_call_id`` is stable per LLM-emitted call).

    We namespace via ``thread_id`` rather than ``checkpoint_ns`` because
    langgraph's ``aget_state`` interprets a non-empty ``checkpoint_ns`` as a
    subgraph path and raises ``ValueError("Subgraph X not found")``.
    """
    merged: dict[str, Any] = dict(runtime.config) if runtime.config else {}
    current_limit = merged.get("recursion_limit")
    try:
        current_int = int(current_limit) if current_limit is not None else 0
    except (TypeError, ValueError):
        current_int = 0
    if current_int < DEFAULT_SUBAGENT_RECURSION_LIMIT:
        merged["recursion_limit"] = DEFAULT_SUBAGENT_RECURSION_LIMIT

    configurable: dict[str, Any] = dict(merged.get("configurable") or {})
    parent_thread_id = configurable.get("thread_id")
    per_call_suffix = f"task:{runtime.tool_call_id}"
    configurable["thread_id"] = (
        f"{parent_thread_id}::{per_call_suffix}"
        if parent_thread_id
        else per_call_suffix
    )
    merged["configurable"] = configurable
    return merged


def consume_surfsense_resume(runtime: ToolRuntime) -> Any:
    """Pop the resume payload for *this* call's ``tool_call_id``.

    The configurable holds ``surfsense_resume_value: dict[tool_call_id, payload]``
    so parallel sibling subagents (each with their own ``tool_call_id``) read
    only their own decision and never race on a shared scalar.
    """
    cfg = runtime.config or {}
    configurable = cfg.get("configurable") if isinstance(cfg, dict) else None
    if not isinstance(configurable, dict):
        return None
    by_tcid = configurable.get("surfsense_resume_value")
    if not isinstance(by_tcid, dict):
        return None
    payload = by_tcid.pop(runtime.tool_call_id, None)
    if not by_tcid:
        configurable.pop("surfsense_resume_value", None)
    return payload


def has_surfsense_resume(runtime: ToolRuntime) -> bool:
    """True iff a resume payload for this call's ``tool_call_id`` is queued (non-destructive)."""
    cfg = runtime.config or {}
    configurable = cfg.get("configurable") if isinstance(cfg, dict) else None
    if not isinstance(configurable, dict):
        return False
    by_tcid = configurable.get("surfsense_resume_value")
    if not isinstance(by_tcid, dict):
        return False
    return runtime.tool_call_id in by_tcid


def drain_parent_null_resume(runtime: ToolRuntime) -> None:
    """Consume the parent's lingering ``NULL_TASK_ID/RESUME`` write before delegating.

    ``stream_resume_chat`` wakes the main agent with
    ``Command(resume={tool_call_id: {"decisions": [...]}})`` so the previously
    propagated parent-level interrupt can return. langgraph stores that
    payload as the parent task's ``null_resume`` pending write. The ``task``
    tool then forwards this turn's slice into the subagent via its own
    ``Command(resume=...)``. While the subagent is mid-execution, any *new*
    ``interrupt()`` inside it (e.g. a follow-up tool call after a mixed
    approve/reject) walks ``subagent_scratchpad → parent_scratchpad.get_null_resume``
    and picks up the parent's still-live decisions — mismatching against a
    different number of hanging tool calls and crashing
    ``HumanInTheLoopMiddleware``.

    Draining the write here closes that cross-graph leak so subagent
    interrupts pause cleanly and bubble back up as a fresh approval card.
    """
    cfg = runtime.config or {}
    configurable = cfg.get("configurable") if isinstance(cfg, dict) else None
    if not isinstance(configurable, dict):
        return
    scratchpad = configurable.get(_LANGGRAPH_SCRATCHPAD_KEY)
    if scratchpad is None:
        return
    consume = getattr(scratchpad, "get_null_resume", None)
    if not callable(consume):
        return
    try:
        consume(True)
    except Exception:
        # Defensive: if langgraph's internal scratchpad shape changes we don't
        # want to break the resume path. Worst case the original ValueError
        # still surfaces — same behavior as before this fix.
        logger.debug(
            "drain_parent_null_resume: scratchpad.get_null_resume raised",
            exc_info=True,
        )
