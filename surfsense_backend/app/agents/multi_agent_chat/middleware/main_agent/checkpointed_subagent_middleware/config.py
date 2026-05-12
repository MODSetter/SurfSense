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
    """RunnableConfig for the nested invoke; raises ``recursion_limit`` to the parent's budget."""
    merged: dict[str, Any] = dict(runtime.config) if runtime.config else {}
    current_limit = merged.get("recursion_limit")
    try:
        current_int = int(current_limit) if current_limit is not None else 0
    except (TypeError, ValueError):
        current_int = 0
    if current_int < DEFAULT_SUBAGENT_RECURSION_LIMIT:
        merged["recursion_limit"] = DEFAULT_SUBAGENT_RECURSION_LIMIT
    return merged


def consume_surfsense_resume(runtime: ToolRuntime) -> Any:
    """Pop the resume payload; siblings share ``configurable`` by reference."""
    cfg = runtime.config or {}
    configurable = cfg.get("configurable") if isinstance(cfg, dict) else None
    if not isinstance(configurable, dict):
        return None
    return configurable.pop("surfsense_resume_value", None)


def has_surfsense_resume(runtime: ToolRuntime) -> bool:
    """True iff a resume payload is queued on this runtime (non-destructive)."""
    cfg = runtime.config or {}
    configurable = cfg.get("configurable") if isinstance(cfg, dict) else None
    if not isinstance(configurable, dict):
        return False
    return "surfsense_resume_value" in configurable


def drain_parent_null_resume(runtime: ToolRuntime) -> None:
    """Consume the parent's lingering ``NULL_TASK_ID/RESUME`` write before delegating.

    ``stream_resume_chat`` wakes the main agent with
    ``Command(resume={"decisions": [...]})`` so the propagated
    ``_lg_interrupt(...)`` can return. langgraph stores that payload as the
    parent task's ``null_resume`` pending write, which only gets consumed
    *after* ``subagent.[a]invoke`` returns (when the post-call propagation
    re-fires). While the subagent is mid-execution, any *new* ``interrupt()``
    inside it (e.g. a follow-up tool call after a mixed approve/reject) walks
    ``subagent_scratchpad → parent_scratchpad.get_null_resume`` and picks up
    the parent's still-live decisions — mismatching against a different number
    of hanging tool calls and crashing ``HumanInTheLoopMiddleware``.

    Draining the write here closes that cross-graph leak so subagent
    interrupts pause cleanly and re-propagate as a fresh approval card.
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
