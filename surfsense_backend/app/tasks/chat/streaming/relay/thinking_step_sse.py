"""Thinking-step SSE plus optional content-builder updates."""

from __future__ import annotations

from typing import Any


def emit_thinking_step_frame(
    *,
    streaming_service: Any,
    content_builder: Any | None,
    step_id: str,
    title: str,
    status: str = "in_progress",
    items: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    if content_builder is not None:
        content_builder.on_thinking_step(
            step_id, title, status, items, metadata=metadata
        )
    return streaming_service.format_thinking_step(
        step_id=step_id,
        title=title,
        status=status,
        items=items,
        metadata=metadata,
    )
