"""Chat model stream: text, reasoning, and tool-call chunk SSE."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from app.tasks.chat.streaming.helpers.chunk_parts import extract_chunk_parts
from app.tasks.chat.streaming.relay.state import AgentEventRelayState
from app.tasks.chat.streaming.relay.task_span import ensure_pending_task_span_for_lc
from app.tasks.chat.streaming.relay.thinking_step_completion import (
    complete_active_thinking_step,
)


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

    reasoning_delta = parts["reasoning"]
    text_delta = parts["text"]

    if reasoning_delta:
        if state.current_text_id is not None:
            yield streaming_service.format_text_end(state.current_text_id)
            if content_builder is not None:
                content_builder.on_text_end(state.current_text_id)
            state.current_text_id = None
        if state.current_reasoning_id is None:
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
            if state.just_finished_tool:
                state.last_active_step_id = None
                state.last_active_step_title = ""
                state.last_active_step_items = []
                state.just_finished_tool = False
            state.current_reasoning_id = streaming_service.generate_reasoning_id()
            yield streaming_service.format_reasoning_start(state.current_reasoning_id)
            if content_builder is not None:
                content_builder.on_reasoning_start(state.current_reasoning_id)
        yield streaming_service.format_reasoning_delta(
            state.current_reasoning_id, reasoning_delta
        )
        if content_builder is not None:
            content_builder.on_reasoning_delta(
                state.current_reasoning_id, reasoning_delta
            )

    if text_delta:
        if state.current_reasoning_id is not None:
            yield streaming_service.format_reasoning_end(state.current_reasoning_id)
            if content_builder is not None:
                content_builder.on_reasoning_end(state.current_reasoning_id)
            state.current_reasoning_id = None
        if state.current_text_id is None:
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
            if state.just_finished_tool:
                state.last_active_step_id = None
                state.last_active_step_title = ""
                state.last_active_step_items = []
                state.just_finished_tool = False
            state.current_text_id = streaming_service.generate_text_id()
            yield streaming_service.format_text_start(state.current_text_id)
            if content_builder is not None:
                content_builder.on_text_start(state.current_text_id)
        yield streaming_service.format_text_delta(state.current_text_id, text_delta)
        state.accumulated_text += text_delta
        if content_builder is not None:
            content_builder.on_text_delta(state.current_text_id, text_delta)

    if parts["tool_call_chunks"]:
        for tcc in parts["tool_call_chunks"]:
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
