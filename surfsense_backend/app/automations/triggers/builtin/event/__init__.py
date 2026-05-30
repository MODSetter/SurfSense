"""``event`` trigger: fire an automation when a matching domain event is published.

Subscribes to the event bus and matches events against a user-authored JSON
filter (see :mod:`.filter`).
"""

from __future__ import annotations

from app.event_bus import bus

from .filter import FilterError, matches
from .inputs import event_runtime_inputs
from .match import trigger_matches_event
from .params import EventTriggerParams
from .source import on_event

__all__ = [
    "EventTriggerParams",
    "FilterError",
    "event_runtime_inputs",
    "matches",
    "trigger_matches_event",
]

# Side-effect: register on the triggers store.
from . import definition  # noqa: F401

# Side-effect: react to published events.
bus.subscribe(on_event)
