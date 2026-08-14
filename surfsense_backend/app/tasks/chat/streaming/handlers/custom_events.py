"""Custom-event payloads turned into SSE (no model/tool stream handling)."""

from __future__ import annotations

from typing import Any

from app.tasks.chat.streaming.relay.activity_sse import emit_activity_frame
from app.tasks.chat.streaming.relay.state import AgentEventRelayState

_PROGRESS_LABELS = {
    "planning": "Planning sections",
    "writing": "Writing sections",
    "revising_section": "Revising a section",
    "adding_section": "Adding a section",
    "removing_section": "Removing a section",
    "discovering": "Finding sources",
    "scraping": "Reviewing sources",
    "processing": "Processing results",
    "verifying": "Checking output",
    "rendering": "Rendering preview",
}


def _trusted_progress_detail(data: dict[str, Any]) -> str | None:
    """Build bounded copy only from allowlisted phases and numeric counters."""
    phase = data.get("phase")
    label = _PROGRESS_LABELS.get(phase) if isinstance(phase, str) else None
    if not label:
        return None
    current = data.get("current")
    total = data.get("total")
    if isinstance(current, int) and current >= 0:
        counter = (
            f"{current}/{total}"
            if isinstance(total, int) and total > 0
            else str(current)
        )
        return f"{label} ({counter})"
    return label


def handle_activity_progress(
    data: dict[str, Any],
    *,
    state: AgentEventRelayState,
    streaming_service: Any,
    content_builder: Any | None,
) -> str | None:
    detail = _trusted_progress_detail(data)
    if not detail:
        return None
    candidates = [
        snapshot
        for snapshot in state.activity_snapshot_by_id.values()
        if snapshot.get("status") in {"running", "awaiting_approval"}
    ]
    if not candidates:
        return None
    current = max(candidates, key=lambda snapshot: snapshot["sequence"])
    snapshot = state.transition_activity(
        current["id"],
        status="running",
        details=[detail],
    )
    if snapshot is None:
        return None
    return emit_activity_frame(
        streaming_service=streaming_service,
        content_builder=content_builder,
        snapshot=snapshot,
    )


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
