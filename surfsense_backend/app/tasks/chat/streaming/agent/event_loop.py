"""Per-turn agent event-loop driver.

Drives ``stream_output`` (graph_stream relay) for one agent turn, then runs the
post-stream agent-state inspection: safety-net commit of any staged filesystem
state (in case ``aafter_agent`` was skipped), file-operation contract scoring,
intent classification, and interrupt detection.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from app.agents.shared.filesystem_selection import FilesystemMode
from app.agents.shared.middleware.kb_persistence import (
    commit_staged_filesystem_state,
)
from app.services.new_streaming_service import VercelStreamingService
from app.tasks.chat.streaming.contract.file_contract import (
    contract_enforcement_active,
    evaluate_file_contract_outcome,
    log_file_contract,
)
from app.tasks.chat.streaming.graph_stream.event_stream import stream_output
from app.tasks.chat.streaming.helpers.interrupt_inspector import (
    all_interrupt_values,
)
from app.tasks.chat.streaming.shared.stream_result import StreamResult
from app.tasks.chat.streaming.shared.utils import safe_float
from app.utils.perf import get_perf_logger

_perf_log = get_perf_logger()


async def stream_agent_events(
    agent: Any,
    config: dict[str, Any],
    input_data: Any,
    streaming_service: VercelStreamingService,
    result: StreamResult,
    step_prefix: str = "thinking",
    initial_step_id: str | None = None,
    initial_step_title: str = "",
    initial_step_items: list[str] | None = None,
    *,
    fallback_commit_search_space_id: int | None = None,
    fallback_commit_created_by_id: str | None = None,
    fallback_commit_filesystem_mode: FilesystemMode = FilesystemMode.CLOUD,
    fallback_commit_thread_id: int | None = None,
    runtime_context: Any = None,
    content_builder: Any | None = None,
) -> AsyncGenerator[str, None]:
    """Stream and format ``astream_events`` from the agent.

    Yields SSE-formatted strings; after exhausting, ``result`` carries
    ``accumulated_text`` and interrupt state. See ``StreamResult`` for the
    side-channel surface populated by the underlying relay.
    """
    async for sse in stream_output(
        agent=agent,
        config=config,
        input_data=input_data,
        streaming_service=streaming_service,
        result=result,
        step_prefix=step_prefix,
        initial_step_id=initial_step_id,
        initial_step_title=initial_step_title,
        initial_step_items=initial_step_items,
        content_builder=content_builder,
        runtime_context=runtime_context,
    ):
        yield sse

    accumulated_text = result.accumulated_text

    state = await agent.aget_state(config)
    state_values = getattr(state, "values", {}) or {}

    # Safety net: if astream_events was cancelled before
    # KnowledgeBasePersistenceMiddleware.aafter_agent ran, any staged work
    # (dirty_paths / staged_dirs / pending_moves / pending_deletes /
    # pending_dir_deletes) is still in the checkpointed state. Run the SAME
    # shared commit helper so the turn's writes don't get lost on client
    # disconnect, then push the delta back into the graph using ``as_node=...``
    # so reducers fire as if the after_agent hook produced it.
    if (
        fallback_commit_filesystem_mode == FilesystemMode.CLOUD
        and fallback_commit_search_space_id is not None
        and (
            (state_values.get("dirty_paths") or [])
            or (state_values.get("staged_dirs") or [])
            or (state_values.get("pending_moves") or [])
            or (state_values.get("pending_deletes") or [])
            or (state_values.get("pending_dir_deletes") or [])
        )
    ):
        try:
            delta = await commit_staged_filesystem_state(
                state_values,
                search_space_id=fallback_commit_search_space_id,
                created_by_id=fallback_commit_created_by_id,
                filesystem_mode=fallback_commit_filesystem_mode,
                thread_id=fallback_commit_thread_id,
                dispatch_events=False,
            )
            if delta:
                await agent.aupdate_state(
                    config,
                    delta,
                    as_node="KnowledgeBasePersistenceMiddleware.after_agent",
                )
        except Exception as exc:
            _perf_log.warning("[stream_agent_events] safety-net commit failed: %s", exc)

    contract_state = state_values.get("file_operation_contract") or {}
    contract_turn_id = contract_state.get("turn_id")
    current_turn_id = config.get("configurable", {}).get("turn_id", "")
    intent_value = contract_state.get("intent")
    if (
        isinstance(intent_value, str)
        and intent_value in ("chat_only", "file_write", "file_read")
        and contract_turn_id == current_turn_id
    ):
        result.intent_detected = intent_value
    if (
        isinstance(intent_value, str)
        and intent_value in ("chat_only", "file_write", "file_read")
        and contract_turn_id != current_turn_id
    ):
        # Ignore stale intent contracts from previous turns/checkpoints.
        result.intent_detected = "chat_only"
    result.intent_confidence = (
        safe_float(contract_state.get("confidence"), default=0.0)
        if contract_turn_id == current_turn_id
        else 0.0
    )

    if result.intent_detected == "file_write":
        result.commit_gate_passed, result.commit_gate_reason = (
            evaluate_file_contract_outcome(result)
        )
        if not result.commit_gate_passed and contract_enforcement_active(result):
            gate_notice = (
                "I could not complete the requested file write because no successful "
                "write_file/edit_file operation was confirmed."
            )
            gate_text_id = streaming_service.generate_text_id()
            yield streaming_service.format_text_start(gate_text_id)
            if content_builder is not None:
                content_builder.on_text_start(gate_text_id)
            yield streaming_service.format_text_delta(gate_text_id, gate_notice)
            if content_builder is not None:
                content_builder.on_text_delta(gate_text_id, gate_notice)
            yield streaming_service.format_text_end(gate_text_id)
            if content_builder is not None:
                content_builder.on_text_end(gate_text_id)
            yield streaming_service.format_terminal_info(gate_notice, "error")
            accumulated_text = gate_notice
    else:
        result.commit_gate_passed = True
        result.commit_gate_reason = ""

    result.accumulated_text = accumulated_text
    log_file_contract("turn_outcome", result)

    pending_values = all_interrupt_values(state)
    if pending_values:
        result.is_interrupted = True
        # One frame per paused subagent so each parallel HITL renders its own
        # approval card on the wire. Order matches ``state.interrupts``, which
        # the resume slicer in
        # ``checkpointed_subagent_middleware.resume_routing`` consumes in the
        # same order — keeping emit and resume in lock-step.
        for interrupt_value in pending_values:
            yield streaming_service.format_interrupt_request(interrupt_value)
