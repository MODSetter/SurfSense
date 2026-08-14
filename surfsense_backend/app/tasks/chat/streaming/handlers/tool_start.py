"""Tool start: thinking-step and tool-input SSE."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from app.tasks.chat.streaming.handlers.tools import resolve_tool_start_thinking
from app.tasks.chat.streaming.helpers.tool_call_matching import (
    match_buffered_langchain_tool_call_id,
)
from app.tasks.chat.streaming.relay.state import AgentEventRelayState
from app.tasks.chat.streaming.relay.task_span import open_task_span
from app.tasks.chat.streaming.relay.thinking_step_completion import (
    complete_active_thinking_step,
)
from app.tasks.chat.streaming.relay.thinking_step_sse import emit_thinking_step_frame

_ARTIFACT_SKILL_PATH = re.compile(
    r"/opt/skills/(?P<skill>pdf|docx|pptx|xlsx)/SKILL\.md(?:\s|['\"]|$)",
    re.IGNORECASE,
)


def _safe_integration_metadata(event: dict[str, Any]) -> dict[str, Any] | None:
    metadata = event.get("metadata")
    if not isinstance(metadata, dict):
        return None
    name = metadata.get("mcp_connector_name")
    is_generic = metadata.get("mcp_is_generic") is True
    if isinstance(name, str) and name.strip():
        return {
            "source": "mcp",
            "key": name.strip().lower().replace(" ", "_"),
            "name": name.strip(),
        }
    if is_generic:
        return {"source": "mcp"}
    return None


def _activity_intent(tool_name: str) -> str | None:
    if tool_name in {"verify_artifact"}:
        return "verify"
    if tool_name in {"save_artifact", "save_document"}:
        return "persist"
    if tool_name.startswith(("read_", "load_", "search_", "grep", "glob", "ls")):
        return "inspect"
    if tool_name in {"execute", "execute_code", "write_file", "edit_file"}:
        return "author"
    return None


def _artifact_skill_name(tool_name: str, tool_input: Any) -> str | None:
    if tool_name not in {"execute", "execute_code"} or not isinstance(
        tool_input, dict
    ):
        return None
    command = tool_input.get("code_or_command")
    if not isinstance(command, str):
        return None
    match = _ARTIFACT_SKILL_PATH.search(command)
    return match.group("skill").lower() if match else None


def iter_tool_start_frames(
    event: dict[str, Any],
    *,
    state: AgentEventRelayState,
    streaming_service: Any,
    content_builder: Any | None,
    result: Any,
    step_prefix: str,
) -> Iterator[str]:
    """SSE frames for the start of one tool run."""
    state.active_tool_depth += 1
    tool_name = event.get("name", "unknown_tool")
    run_id = event.get("run_id", "")
    tool_input = event.get("data", {}).get("input", {})
    started_at = datetime.now(UTC).isoformat()
    if run_id:
        state.tool_started_at_by_run[run_id] = started_at
    if tool_name in ("write_file", "edit_file"):
        result.write_attempted = True
        if isinstance(tool_input, dict):
            file_path = tool_input.get("file_path")
            if isinstance(file_path, str) and file_path.strip() and run_id:
                state.file_path_by_run[run_id] = file_path.strip()

    if state.current_text_id is not None:
        yield streaming_service.format_text_end(state.current_text_id)
        if content_builder is not None:
            content_builder.on_text_end(state.current_text_id)
        state.current_text_id = None

    if (
        state.active_tool_depth == 1
        and state.last_active_step_title != "Synthesizing response"
    ):
        comp, new_active = complete_active_thinking_step(
            state=state,
            streaming_service=streaming_service,
            content_builder=content_builder,
            last_active_step_id=state.last_active_step_id,
            last_active_step_title=state.last_active_step_title,
            last_active_step_items=state.last_active_step_items,
            completed_step_ids=state.completed_step_ids,
        )
        if comp:
            yield comp
        state.last_active_step_id = new_active

    state.just_finished_tool = False
    tool_step_id = state.next_thinking_step_id(step_prefix)
    state.tool_step_ids[run_id] = tool_step_id
    state.last_active_step_id = tool_step_id

    matched_meta: dict[str, str] | None = None
    taken_ui_ids = set(state.ui_tool_call_id_by_run.values())
    for meta in state.index_to_meta.values():
        if meta["name"] == tool_name and meta["ui_id"] not in taken_ui_ids:
            matched_meta = meta
            break

    tool_call_id: str
    langchain_tool_call_id: str | None = None
    if matched_meta is not None:
        tool_call_id = matched_meta["ui_id"]
        langchain_tool_call_id = matched_meta["lc_id"]
        if run_id:
            state.lc_tool_call_id_by_run[run_id] = matched_meta["lc_id"]
    else:
        tool_call_id = (
            f"call_{run_id[:32]}"
            if run_id
            else streaming_service.generate_tool_call_id()
        )
        langchain_tool_call_id = match_buffered_langchain_tool_call_id(
            state.pending_tool_call_chunks,
            tool_name,
            run_id,
            state.lc_tool_call_id_by_run,
        )

    if tool_name == "task":
        open_task_span(
            state,
            run_id=run_id,
            langchain_tool_call_id=langchain_tool_call_id,
        )
        if isinstance(tool_input, dict):
            subagent_type = tool_input.get("subagent_type")
            if isinstance(subagent_type, str) and subagent_type.strip():
                state.active_subagent_type = subagent_type.strip()

    tool_md = state.tool_activity_metadata(thinking_step_id=tool_step_id) or {}
    tool_md["startedAt"] = started_at
    integration = _safe_integration_metadata(event)
    if integration:
        tool_md["integration"] = integration
    skill_name = _artifact_skill_name(tool_name, tool_input)
    intent = "discover_skill" if skill_name else _activity_intent(tool_name)
    if intent:
        context = dict(tool_md.get("context") or {})
        context["intent"] = intent
        if skill_name:
            context["skillName"] = skill_name
        tool_md["context"] = context

    if matched_meta is None:
        yield streaming_service.format_tool_input_start(
            tool_call_id,
            tool_name,
            langchain_tool_call_id=langchain_tool_call_id,
            metadata=tool_md,
        )
        if content_builder is not None:
            content_builder.on_tool_input_start(
                tool_call_id,
                tool_name,
                langchain_tool_call_id,
                metadata=tool_md,
            )

    thinking = resolve_tool_start_thinking(tool_name, tool_input)
    state.last_active_step_title = thinking.title
    state.last_active_step_items = thinking.items
    if run_id:
        state.tool_step_items_by_run[run_id] = list(thinking.items)
    frame_kw: dict[str, Any] = {
        "streaming_service": streaming_service,
        "content_builder": content_builder,
        "step_id": tool_step_id,
        "title": thinking.title,
        "status": "in_progress",
        "metadata": tool_md,
    }
    if thinking.include_items_on_frame:
        frame_kw["items"] = thinking.items
    yield emit_thinking_step_frame(**frame_kw)

    if run_id:
        state.ui_tool_call_id_by_run[run_id] = tool_call_id

    if isinstance(tool_input, dict):
        _safe_input: dict[str, Any] = {}
        for _k, _v in tool_input.items():
            try:
                json.dumps(_v)
                _safe_input[_k] = _v
            except (TypeError, ValueError, OverflowError):
                pass
    else:
        _safe_input = {"input": tool_input}
    yield streaming_service.format_tool_input_available(
        tool_call_id,
        tool_name,
        _safe_input,
        langchain_tool_call_id=langchain_tool_call_id,
        metadata=tool_md,
    )
    if content_builder is not None:
        content_builder.on_tool_input_available(
            tool_call_id,
            tool_name,
            _safe_input,
            langchain_tool_call_id,
            metadata=tool_md,
        )
