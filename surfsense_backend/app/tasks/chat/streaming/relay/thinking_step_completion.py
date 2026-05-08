"""Close the in-progress thinking step with a completed status frame."""

from __future__ import annotations

from typing import Any

from .state import AgentEventRelayState
from .thinking_step_sse import emit_thinking_step_frame


def complete_active_thinking_step(
    *,
    state: AgentEventRelayState,
    streaming_service: Any,
    content_builder: Any | None,
    last_active_step_id: str | None,
    last_active_step_title: str,
    last_active_step_items: list[str],
    completed_step_ids: set[str],
) -> tuple[str | None, str | None]:
    """Emit a completed thinking-step frame once; return (frame or None, next active step id)."""
    if last_active_step_id and last_active_step_id not in completed_step_ids:
        completed_step_ids.add(last_active_step_id)
        event = emit_thinking_step_frame(
            streaming_service=streaming_service,
            content_builder=content_builder,
            step_id=last_active_step_id,
            title=last_active_step_title,
            status="completed",
            items=last_active_step_items if last_active_step_items else None,
            metadata=state.span_metadata_if_active(),
        )
        return event, None
    return None, last_active_step_id
