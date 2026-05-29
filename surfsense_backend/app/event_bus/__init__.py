"""In-process domain event bus.

Domain-agnostic pub/sub. Producers ``await bus.publish(...)``; subscribers
``bus.subscribe(...)``. Domain modules depend on it, never the reverse.

    from app.event_bus import bus
    await bus.publish("document.indexed", {"document_id": 42}, search_space_id=7)
"""

from __future__ import annotations

from .bus import EventBus, Subscriber, bus
from .event import Event

__all__ = [
    "Event",
    "EventBus",
    "Subscriber",
    "bus",
]
