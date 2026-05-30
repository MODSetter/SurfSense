"""Pure predicate: does an event trigger fire for a given event?"""

from __future__ import annotations

from typing import Any

from app.event_bus import Event

from .filter import matches


def trigger_matches_event(params: dict[str, Any], event: Event) -> bool:
    """True when an event trigger configured with ``params`` should fire for ``event``."""
    if params.get("event_type") != event.event_type:
        return False
    return matches(params.get("filter") or {}, event.payload)
