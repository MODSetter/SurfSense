"""Chat model stream: text, reasoning, and tool-call chunk SSE."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from app.tasks.chat.streaming.helpers.chunk_parts import extract_chunk_parts
from app.tasks.chat.streaming.relay.activity_sse import emit_activity_frame
from app.tasks.chat.streaming.relay.state import AgentEventRelayState
from app.tasks.chat.streaming.relay.task_span import ensure_pending_task_span_for_lc


def iter_chat_model_stream_frames(
    event: dict[str, Any],
    *,
    state: AgentEventRelayState,
    streaming_service: Any,
    content_builder: Any | None,
    step_prefix: str,
) -> Iterator[str]:
    """SSE frames for one chat-model chunk."""
    if state.active_tool_depth > 0:
        return
    if "surfsense:internal" in event.get("tags", []):
        return
    chunk = event.get("data", {}).get("chunk")
    if not chunk:
        return
    parts = extract_chunk_parts(chunk)

    for part_type, value in parts["ordered"]:
        if part_type == "reasoning":
            if state.current_text_id is not None:
                yield streaming_service.format_text_end(state.current_text_id)
                if content_builder is not None:
                    content_builder.on_text_end(state.current_text_id)
                state.current_text_id = None
            if state.current_reasoning_id is None:
                for snapshot in state.journal.complete_open_phases(
                    completed_at=datetime.now(UTC).isoformat()
                ):
                    yield emit_activity_frame(
                        streaming_service=streaming_service,
                        content_builder=content_builder,
                        snapshot=snapshot,
                    )
                state.current_reasoning_id = streaming_service.generate_reasoning_id()
                yield streaming_service.format_reasoning_start(
                    state.current_reasoning_id
                )
                if content_builder is not None:
                    content_builder.on_reasoning_start(state.current_reasoning_id)
            yield streaming_service.format_reasoning_delta(
                state.current_reasoning_id, value
            )
            if content_builder is not None:
                content_builder.on_reasoning_delta(state.current_reasoning_id, value)
            continue

        if part_type == "text":
            if state.current_reasoning_id is not None:
                yield streaming_service.format_reasoning_end(state.current_reasoning_id)
                if content_builder is not None:
                    content_builder.on_reasoning_end(state.current_reasoning_id)
                state.current_reasoning_id = None
            if state.current_text_id is None:
                for snapshot in state.journal.complete_open_phases(
                    completed_at=datetime.now(UTC).isoformat()
                ):
                    yield emit_activity_frame(
                        streaming_service=streaming_service,
                        content_builder=content_builder,
                        snapshot=snapshot,
                    )
                state.current_text_id = streaming_service.generate_text_id()
                yield streaming_service.format_text_start(state.current_text_id)
                if content_builder is not None:
                    content_builder.on_text_start(state.current_text_id)
            yield streaming_service.format_text_delta(state.current_text_id, value)
            state.accumulated_text += value
            if content_builder is not None:
                content_builder.on_text_delta(state.current_text_id, value)
            continue

        if part_type == "tool_call_chunk":
            tcc = value
            idx = tcc.get("index")

            if idx is not None and idx not in state.index_to_meta:
                lc_id = tcc.get("id")
                name = tcc.get("name")
                if lc_id and name:
                    ui_id = lc_id
                    tool_input_metadata: dict[str, Any] | None = None
                    if name == "task":
                        sid = ensure_pending_task_span_for_lc(state, str(lc_id))
                        tool_input_metadata = {"spanId": sid}

                    if state.current_text_id is not None:
                        yield streaming_service.format_text_end(state.current_text_id)
                        if content_builder is not None:
                            content_builder.on_text_end(state.current_text_id)
                        state.current_text_id = None
                    if state.current_reasoning_id is not None:
                        yield streaming_service.format_reasoning_end(
                            state.current_reasoning_id
                        )
                        if content_builder is not None:
                            content_builder.on_reasoning_end(state.current_reasoning_id)
                        state.current_reasoning_id = None

                    state.index_to_meta[idx] = {
                        "ui_id": ui_id,
                        "lc_id": lc_id,
                        "name": name,
                    }
                    yield streaming_service.format_tool_input_start(
                        ui_id,
                        name,
                        langchain_tool_call_id=lc_id,
                        metadata=tool_input_metadata,
                    )
                    if content_builder is not None:
                        content_builder.on_tool_input_start(
                            ui_id, name, lc_id, metadata=tool_input_metadata
                        )

            meta = state.index_to_meta.get(idx) if idx is not None else None
            if meta:
                args_chunk = tcc.get("args") or ""
                if args_chunk:
                    yield streaming_service.format_tool_input_delta(
                        meta["ui_id"], args_chunk
                    )
                    if content_builder is not None:
                        content_builder.on_tool_input_delta(meta["ui_id"], args_chunk)
            else:
                state.pending_tool_call_chunks.append(tcc)
