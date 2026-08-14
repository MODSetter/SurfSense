"""Custom graph events routed to SSE (documents, action logs, report progress)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from app.tasks.chat.streaming.handlers.custom_events import (
    handle_action_log,
    handle_action_log_updated,
    handle_activity_progress,
    handle_document_created,
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

    if name in {"report_progress", "scraper_progress", "verification_progress"}:
        frame = handle_activity_progress(
            data,
            state=state,
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
