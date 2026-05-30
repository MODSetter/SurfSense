"""Build run inputs from a published event."""

from __future__ import annotations

from typing import Any

from app.event_bus import Event


def event_runtime_inputs(event: Event) -> dict[str, Any]:
    """Flatten the event payload and stamp event metadata as run inputs."""
    return {
        **event.payload,
        "event_type": event.event_type,
        "event_id": event.event_id,
        "occurred_at": event.occurred_at.isoformat(),
    }
