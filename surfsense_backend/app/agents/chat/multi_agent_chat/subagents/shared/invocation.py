"""Subagent-invocation contract shared by the orchestrator and nested subagents.

Both the main-agent ``task`` middleware (``checkpointed_subagent_middleware``)
and subagents that themselves invoke another subagent (e.g.
``ask_knowledge_base``) need the same two things when spawning a child run:

- a ``RunnableConfig`` that raises the recursion limit and isolates the child's
  ``thread_id`` so each invocation lands in its own checkpoint slot
  (``subagent_invoke_config``), and
- the set of parent state keys that must *not* be forwarded into / merged back
  from the child (``EXCLUDED_STATE_KEYS``).

Keeping this here (rather than inside the main-agent middleware) lets subagents
reuse the contract without importing main-agent internals.
"""

from __future__ import annotations

from typing import Any

from langchain.tools import ToolRuntime

# Mirror of deepagents.middleware.subagents._EXCLUDED_STATE_KEYS.
EXCLUDED_STATE_KEYS = frozenset(
    {
        "messages",
        "todos",
        "structured_response",
        "skills_metadata",
        "memory_contents",
    }
)

# Match the parent graph's budget; the LangGraph default of 25 trips on
# multi-step subagent runs.
DEFAULT_SUBAGENT_RECURSION_LIMIT = 10_000


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
