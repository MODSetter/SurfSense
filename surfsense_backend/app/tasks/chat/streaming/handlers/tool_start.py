"""Tool start: canonical activity and tool-input SSE."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from app.services.streaming.types import ActivityIntegration
from app.tasks.chat.streaming.handlers.tools.activity import resolve_tool_activity
from app.tasks.chat.streaming.helpers.tool_call_matching import (
    match_buffered_langchain_tool_call_id,
)
from app.tasks.chat.streaming.relay.activity_sse import emit_activity_frame
from app.tasks.chat.streaming.relay.state import AgentEventRelayState
from app.tasks.chat.streaming.relay.task_span import open_task_span


def _safe_integration_metadata(
    event: dict[str, Any],
) -> ActivityIntegration | None:
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


def _artifact_instruction_type(tool_name: str, tool_input: Any) -> str | None:
    if tool_name != "load_artifact_instructions" or not isinstance(tool_input, dict):
        return None
    artifact_type = tool_input.get("artifact_type")
    return artifact_type if artifact_type in {"pdf", "docx", "pptx", "xlsx"} else None


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

    artifact_type = _artifact_instruction_type(tool_name, tool_input)
    event_metadata = event.get("metadata")
    trusted_descriptor = (
        event_metadata.get("activity_descriptor")
        if isinstance(event_metadata, dict)
        else None
    )
    activity = resolve_tool_activity(
        tool_name,
        subagent_type=state.active_subagent_type,
        artifact_type=artifact_type,
        repairing_artifact=state.deliverable_needs_repair,
        trusted_descriptor=trusted_descriptor,
    )
    integration = _safe_integration_metadata(event)
    activity_id: str | None = None
    if activity.visibility != "hide":
        scope = state.active_span_id or "root"
        phase_key = activity.phase_key if activity.lifecycle == "phase" else None
        open_phase = state.open_phase_by_scope.get(scope)
        reuse_phase = bool(
            phase_key
            and open_phase
            and open_phase[0] == phase_key
            and open_phase[1] not in state.terminal_activity_ids
        )
        if open_phase and not reuse_phase:
            closed = state.transition_activity(
                open_phase[1], status="completed", completed_at=started_at
            )
            if closed:
                yield emit_activity_frame(
                    streaming_service=streaming_service,
                    content_builder=content_builder,
                    snapshot=closed,
                )
        if reuse_phase and open_phase:
            activity_id = open_phase[1]
            snapshot = state.activity_snapshot_by_id[activity_id]
        else:
            resumable_ids = state.resumable_activity_ids_by_kind.get(activity.kind)
            activity_id = (
                resumable_ids.pop(0)
                if resumable_ids
                else state.next_activity_id(step_prefix)
            )
            previous = state.activity_snapshot_by_id.get(activity_id)
            snapshot = activity.snapshot(
                activity_id=activity_id,
                sequence=(previous["sequence"] if previous else state.activity_counter),
                status="running",
                started_at=previous["startedAt"] if previous else started_at,
                integration=integration
                or (previous.get("integration") if previous else None),
            )
            state.activity_spec_by_id[activity_id] = activity
            state.activity_snapshot_by_id[activity_id] = snapshot
            if phase_key:
                state.open_phase_by_scope[scope] = (phase_key, activity_id)
        if run_id:
            state.activity_id_by_run[run_id] = activity_id
        yield emit_activity_frame(
            streaming_service=streaming_service,
            content_builder=content_builder,
            snapshot=snapshot,
        )

    tool_md = state.tool_activity_metadata(activity_id=activity_id) or {}

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
