"""Keep canonical activity persistence and SSE emission in lockstep."""

from __future__ import annotations

from typing import Any

from app.services.streaming.types import ActivityData, ActivityTimingData
from app.tasks.chat.streaming.activity_timing import ActivityTimer


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


def emit_completed_activity_timing_frame(
    *,
    streaming_service: Any,
    content_builder: Any | None,
    timer: ActivityTimer,
    now_ns: int | None = None,
) -> str:
    """Strictly complete a successful turn and dual-write its terminal snapshot."""
    return emit_activity_timing_frame(
        streaming_service=streaming_service,
        content_builder=content_builder,
        snapshot=timer.complete(now_ns=now_ns),
    )


def emit_completed_activity_timing_frame_if_running(
    *,
    streaming_service: Any,
    content_builder: Any | None,
    timer: ActivityTimer,
    now_ns: int | None = None,
) -> str | None:
    """Complete exception cleanup once without changing paused/terminal timers."""
    snapshot = timer.complete_if_running(now_ns=now_ns)
    if snapshot is None:
        return None
    return emit_activity_timing_frame(
        streaming_service=streaming_service,
        content_builder=content_builder,
        snapshot=snapshot,
    )
