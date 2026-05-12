"""Open/close ``active_span_id`` around a delegating ``task`` tool run."""

from __future__ import annotations

import uuid

from app.tasks.chat.streaming.relay.state import AgentEventRelayState


def new_span_id() -> str:
    """One delegation-episode id (shared by activity under an open ``task``)."""
    return f"spn_{uuid.uuid4().hex}"


def _run_key(run_id: str) -> str:
    return (run_id or "").strip()


def _lc_key(langchain_tool_call_id: str | None) -> str:
    return (langchain_tool_call_id or "").strip()


def ensure_pending_task_span_for_lc(state: AgentEventRelayState, lc_id: str) -> str:
    """Return span id for this LangChain tool call id, storing it in ``pending`` if new.

    Used from ``chat_model_stream`` when the first ``task`` chunk registers so
    early ``tool-input-start`` can carry ``metadata.spanId`` before ``on_tool_start``.
    """
    key = _lc_key(lc_id)
    if not key:
        return new_span_id()
    existing = state.pending_task_span_by_lc.get(key)
    if existing:
        return existing
    sid = new_span_id()
    state.pending_task_span_by_lc[key] = sid
    return sid


def open_task_span(
    state: AgentEventRelayState,
    *,
    run_id: str,
    langchain_tool_call_id: str | None = None,
) -> str:
    """Set ``active_span_id`` from pending (same lc) or mint; remember ``active_task_run_id``.

    Call when the ``task`` tool **starts**. Nested ``task`` is not supported:
    a second call replaces the previous span without restoring it.
    """
    key = _lc_key(langchain_tool_call_id)
    sid: str | None = state.pending_task_span_by_lc.pop(key, None) if key else None
    if not sid:
        sid = new_span_id()
    state.active_span_id = sid
    state.active_task_run_id = _run_key(run_id) or None
    return sid


def clear_task_span_if_delegating_task_ended(
    state: AgentEventRelayState,
    *,
    tool_name: str,
    run_id: str,
) -> None:
    """Clear span state only when this event is the end of the opening ``task`` run."""
    if tool_name != "task":
        return
    if state.active_task_run_id is None:
        return
    if state.active_task_run_id != _run_key(run_id):
        return
    state.active_span_id = None
    state.active_task_run_id = None
