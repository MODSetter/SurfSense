"""Event type catalog: the deliberate contract behind each event.

``EventType`` declares a dotted name and the shape of its payload.
``EventCatalog`` is the registry — populated once at import by each event type
module. ``catalog`` is the process-wide singleton.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


@dataclass(frozen=True, slots=True)
class EventType:
    type: str
    description: str
    payload_model: type[BaseModel]

    @property
    def payload_schema(self) -> dict[str, Any]:
        """JSON Schema (draft 2020-12) derived from ``payload_model``."""
        return self.payload_model.model_json_schema()


class EventCatalog:
    """Registry of known event types. Populated at import; read at runtime."""

    def __init__(self) -> None:
        self._registry: dict[str, EventType] = {}

    def register(self, event_type: EventType) -> None:
        """Register an event type. Raises on duplicate type."""
        if event_type.type in self._registry:
            raise ValueError(f"Event type already registered: {event_type.type!r}")
        self._registry[event_type.type] = event_type

    def get(self, type_: str) -> EventType | None:
        return self._registry.get(type_)

    def all(self) -> dict[str, EventType]:
        """Defensive snapshot of the registry."""
        return dict(self._registry)


catalog = EventCatalog()
