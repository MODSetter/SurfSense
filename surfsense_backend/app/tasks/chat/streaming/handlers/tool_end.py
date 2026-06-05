"""Tool end: thinking completion, tool output, and terminal SSE."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from langchain_core.messages import ToolMessage
from langgraph.types import Command

from app.tasks.chat.streaming.handlers.tools import (
    ToolCompletionEmissionContext,
    iter_tool_completion_emission_frames,
    resolve_tool_completed_thinking_step,
)
from app.tasks.chat.streaming.helpers.tool_output import tool_output_has_error
from app.tasks.chat.streaming.relay.state import AgentEventRelayState
from app.tasks.chat.streaming.relay.task_span import (
    clear_task_span_if_delegating_task_ended,
)
from app.tasks.chat.streaming.relay.thinking_step_sse import emit_thinking_step_frame


def _unwrap_command_output(raw_output: Any) -> Any:
    """Replace a ``Command`` from a tool return with its inner ``ToolMessage``.

    Tools that participate in receipt-style state writes (see
    ``app.agents.chat.multi_agent_chat.shared.receipts.command.with_receipt``) return a
    ``Command(update={"messages": [ToolMessage(...)], "receipts": [...]})``.
    LangChain's ``on_tool_end`` event surfaces that ``Command`` verbatim as
    ``data.output``, which the rest of this handler can't introspect: it has
    no ``.content``, isn't a ``dict``, and stringifies to ``"Command(...)"``.
    That stringified payload reaches the frontend and breaks tool-specific
    UI components (e.g. the podcast card) that look for ``status`` /
    ``podcast_id`` at the top level.

    We extract the first ``ToolMessage`` from the Command's ``messages`` list
    so downstream code can read ``.content`` normally. Commands that don't
    contain a ``ToolMessage`` (rare, e.g. pure state updates) are returned
    unchanged — the existing ``str(raw_output)`` fallback handles them.
    """
    if not isinstance(raw_output, Command):
        return raw_output
    update = raw_output.update
    if not isinstance(update, dict):
        return raw_output
    messages = update.get("messages")
    if not isinstance(messages, list):
        return raw_output
    for msg in messages:
        if isinstance(msg, ToolMessage):
            return msg
    return raw_output


def iter_tool_end_frames(
    event: dict[str, Any],
    *,
    state: AgentEventRelayState,
    streaming_service: Any,
    content_builder: Any | None,
    result: Any,
    step_prefix: str,
    config: dict[str, Any],
) -> Iterator[str]:
    """SSE frames when one tool run finishes."""
    state.active_tool_depth = max(0, state.active_tool_depth - 1)
    run_id = event.get("run_id", "")
    tool_name = event.get("name", "unknown_tool")
    raw_output = _unwrap_command_output(event.get("data", {}).get("output", ""))
    staged_file_path = state.file_path_by_run.pop(run_id, None) if run_id else None

    if hasattr(raw_output, "content"):
        content = raw_output.content
        if isinstance(content, str):
            try:
                tool_output = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                tool_output = {"result": content}
        elif isinstance(content, dict):
            tool_output = content
        else:
            tool_output = {"result": str(content)}
    elif isinstance(raw_output, dict):
        tool_output = raw_output
    else:
        tool_output = {"result": str(raw_output) if raw_output else "completed"}

    if tool_name in ("write_file", "edit_file"):
        if tool_output_has_error(tool_output):
            pass
        else:
            result.write_succeeded = True
            result.verification_succeeded = True

    tool_call_id = state.ui_tool_call_id_by_run.get(
        run_id,
        f"call_{run_id[:32]}" if run_id else "call_unknown",
    )
    original_step_id = state.tool_step_ids.get(
        run_id, f"{step_prefix}-unknown-{run_id[:8]}"
    )
    state.completed_step_ids.add(original_step_id)

    holder = state.current_lc_tool_call_id
    holder["value"] = None
    authoritative = getattr(raw_output, "tool_call_id", None)
    if isinstance(authoritative, str) and authoritative:
        holder["value"] = authoritative
        if run_id:
            state.lc_tool_call_id_by_run[run_id] = authoritative
    elif run_id and run_id in state.lc_tool_call_id_by_run:
        holder["value"] = state.lc_tool_call_id_by_run[run_id]

    items = state.last_active_step_items
    title, completed_items = resolve_tool_completed_thinking_step(
        tool_name, tool_output, items
    )
    yield emit_thinking_step_frame(
        streaming_service=streaming_service,
        content_builder=content_builder,
        step_id=original_step_id,
        title=title,
        status="completed",
        items=completed_items,
        metadata=state.span_metadata_if_active(),
    )

    state.just_finished_tool = True
    state.last_active_step_id = None
    state.last_active_step_title = ""
    state.last_active_step_items = []

    emission_ctx = ToolCompletionEmissionContext(
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        tool_output=tool_output,
        streaming_service=streaming_service,
        content_builder=content_builder,
        langchain_tool_call_id_holder=holder,
        stream_result=result,
        langgraph_config=config,
        staged_workspace_file_path=staged_file_path,
        tool_metadata=state.tool_activity_metadata(
            thinking_step_id=original_step_id,
        ),
    )
    yield from iter_tool_completion_emission_frames(emission_ctx)

    clear_task_span_if_delegating_task_ended(state, tool_name=tool_name, run_id=run_id)
