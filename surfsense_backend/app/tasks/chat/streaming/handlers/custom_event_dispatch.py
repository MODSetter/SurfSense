"""Custom graph events routed to SSE (documents, action logs, report progress)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from app.tasks.chat.streaming.handlers.custom_events import (
    handle_action_log,
    handle_action_log_updated,
    handle_document_created,
    handle_report_progress,
)
from app.tasks.chat.streaming.relay.state import AgentEventRelayState


def iter_custom_event_frames(
    event: dict[str, Any],
    *,
    state: AgentEventRelayState,
    streaming_service: Any,
    content_builder: Any | None,
) -> Iterator[str]:
    """Yield any SSE produced by ad-hoc graph events (documents, action logs, report progress)."""
    name = event.get("name")
    data = event.get("data", {})

    if name == "report_progress":
        frame, state.last_active_step_items = handle_report_progress(
            data,
            last_active_step_id=state.last_active_step_id,
            last_active_step_title=state.last_active_step_title,
            last_active_step_items=state.last_active_step_items,
            streaming_service=streaming_service,
            content_builder=content_builder,
        )
        if frame:
            yield frame
        return

    if name == "document_created":
        frame = handle_document_created(data, streaming_service=streaming_service)
        if frame:
            yield frame
        return

    if name == "action_log":
        frame = handle_action_log(data, streaming_service=streaming_service)
        if frame:
            yield frame
        return

    if name == "action_log_updated":
        frame = handle_action_log_updated(data, streaming_service=streaming_service)
        if frame:
            yield frame
