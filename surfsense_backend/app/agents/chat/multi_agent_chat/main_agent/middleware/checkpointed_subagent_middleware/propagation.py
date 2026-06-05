"""Stamp the parent's ``tool_call_id`` onto a subagent's pending interrupt value.

When a subagent (compiled as a langgraph subgraph and invoked from a parent
tool node) hits an ``interrupt(...)`` from its HITL middleware, langgraph
raises ``GraphInterrupt`` out of ``subagent.[a]invoke(...)``. The parent's
``task`` tool catches that exception, stamps ``tool_call_id`` onto each
``Interrupt.value`` using :func:`wrap_with_tool_call_id`, and re-raises a
fresh ``GraphInterrupt`` whose values carry that stamp.

``stream_resume_chat`` then reads ``parent.state.interrupts[*].value["tool_call_id"]``
to route a flat ``decisions`` list back to the right paused subagent — without
the stamp, parallel HITL across siblings would collapse into an ambiguous
bucket and resume would fail.

This module hosts only the stamping helper; the catch/re-raise lives in
``task_tool.py`` since that's the single chokepoint where the raw exception
is in our hands.
"""

from __future__ import annotations

from typing import Any


def wrap_with_tool_call_id(value: Any, tool_call_id: str) -> dict[str, Any]:
    """Return a value dict that always carries the parent's ``tool_call_id``.

    Dict values are shallow-copied with ``tool_call_id`` stamped on top, so
    any value the subagent may already carry under that key (from a deeper
    HITL level) is overwritten — the parent's call id is the only one
    ``stream_resume_chat`` correlates against.

    Non-dict values are wrapped as ``{"value": <original>, "tool_call_id": ...}``
    so simple ``interrupt("approve?")`` patterns still propagate cleanly.
    """
    if isinstance(value, dict):
        return {**value, "tool_call_id": tool_call_id}
    return {"value": value, "tool_call_id": tool_call_id}
