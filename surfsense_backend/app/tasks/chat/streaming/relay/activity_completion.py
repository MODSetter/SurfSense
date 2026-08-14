"""Terminal transitions for open semantic activity phases."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from app.tasks.chat.streaming.relay.activity_sse import emit_activity_frame
from app.tasks.chat.streaming.relay.state import AgentEventRelayState


def iter_complete_open_activity_frames(
    *,
    state: AgentEventRelayState,
    streaming_service: Any,
    content_builder: Any | None,
) -> Iterator[str]:
    completed_at = datetime.now(UTC).isoformat()
    for _, activity_id in list(state.open_phase_by_scope.values()):
        snapshot = state.transition_activity(
            activity_id,
            status="completed",
            completed_at=completed_at,
        )
        if snapshot:
            yield emit_activity_frame(
                streaming_service=streaming_service,
                content_builder=content_builder,
                snapshot=snapshot,
            )
