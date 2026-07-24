"""Custom-event payloads turned into SSE (no model/tool stream handling)."""

from __future__ import annotations

from typing import Any

from app.tasks.chat.streaming.relay.thinking_step_sse import emit_thinking_step_frame


def handle_report_progress(
    data: dict[str, Any],
    *,
    last_active_step_id: str | None,
    last_active_step_title: str,
    last_active_step_items: list[str],
    streaming_service: Any,
    content_builder: Any | None,
    thinking_metadata: dict[str, Any] | None = None,
) -> tuple[str | None, list[str]]:
    """Update report step items; may emit one thinking SSE frame.

    Returns (frame or None, items list after update).
    """
    message = data.get("message", "")
    if not message or not last_active_step_id:
        return None, last_active_step_items

    phase = data.get("phase", "")
    topic_items = [item for item in last_active_step_items if item.startswith("Topic:")]

    if phase in ("revising_section", "adding_section"):
        plan_items = [
            item
            for item in last_active_step_items
            if item.startswith("Topic:")
            or item.startswith("Modifying ")
            or item.startswith("Adding ")
            or item.startswith("Removing ")
        ]
        plan_items = [item for item in plan_items if not item.endswith("...")]
        new_items = [*plan_items, message]
    else:
        new_items = [*topic_items, message]

    frame = emit_thinking_step_frame(
        streaming_service=streaming_service,
        content_builder=content_builder,
        step_id=last_active_step_id,
        title=last_active_step_title,
        status="in_progress",
        items=new_items,
        metadata=thinking_metadata,
    )
    return frame, new_items


def _scraper_progress_label(data: dict[str, Any]) -> str:
    """Build a one-line human status from a ``scraper_progress`` event."""
    message = data.get("message")
    phase = data.get("phase", "")
    current = data.get("current")
    total = data.get("total")
    label = message or (phase.replace("_", " ").capitalize() if phase else "Working")
    if current is not None:
        counter = f"{current}/{total}" if total else str(current)
        label = f"{label} ({counter})"
    return label


def handle_scraper_progress(
    data: dict[str, Any],
    *,
    last_active_step_id: str | None,
    last_active_step_title: str,
    last_active_step_items: list[str],
    streaming_service: Any,
    content_builder: Any | None,
    thinking_metadata: dict[str, Any] | None = None,
) -> tuple[str | None, list[str]]:
    """Surface a scraper's live progress as an evolving thinking-step item.

    Scraper capability tool calls own a fresh thinking step (see ``tool_start``),
    so we show a single latest-status line rather than accumulating every event.
    Returns (frame or None, items after update).
    """
    if not last_active_step_id:
        return None, last_active_step_items
    label = _scraper_progress_label(data)
    if not label:
        return None, last_active_step_items
    new_items = [label]
    frame = emit_thinking_step_frame(
        streaming_service=streaming_service,
        content_builder=content_builder,
        step_id=last_active_step_id,
        title=last_active_step_title,
        status="in_progress",
        items=new_items,
        metadata=thinking_metadata,
    )
    return frame, new_items


def handle_document_created(
    data: dict[str, Any], *, streaming_service: Any
) -> str | None:
    if not data.get("id"):
        return None
    return streaming_service.format_data(
        "documents-updated",
        {"action": "created", "document": data},
    )


def handle_action_log(data: dict[str, Any], *, streaming_service: Any) -> str | None:
    if data.get("id") is None:
        return None
    return streaming_service.format_data("action-log", data)


def handle_action_log_updated(
    data: dict[str, Any], *, streaming_service: Any
) -> str | None:
    if data.get("id") is None:
        return None
    return streaming_service.format_data("action-log-updated", data)
