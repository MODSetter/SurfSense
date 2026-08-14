"""Keep canonical activity persistence and SSE emission in lockstep."""

from __future__ import annotations

from typing import Any

from app.services.streaming.types import ActivityData, ActivityTimingData


def emit_activity_frame(
    *,
    streaming_service: Any,
    content_builder: Any | None,
    snapshot: ActivityData,
) -> str:
    if content_builder is not None:
        content_builder.on_activity(snapshot)
    return streaming_service.format_activity(snapshot)


def emit_activity_timing_frame(
    *,
    streaming_service: Any,
    content_builder: Any | None,
    snapshot: ActivityTimingData,
) -> str:
    if content_builder is not None:
        content_builder.on_activity_timing(snapshot)
    return streaming_service.format_data("activity-timing", snapshot)
