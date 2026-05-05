"""RunnableConfig wiring for nested subagent invocations.

Forwards the parent's ``runtime.config`` (thread_id, …) into the subagent and
exposes the side-channel ``stream_resume_chat`` uses to ferry resume payloads.
"""

from __future__ import annotations

from typing import Any

from langchain.tools import ToolRuntime

from .constants import DEFAULT_SUBAGENT_RECURSION_LIMIT


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
