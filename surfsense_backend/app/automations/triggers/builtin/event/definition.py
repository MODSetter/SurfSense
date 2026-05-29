"""``event`` ``TriggerDefinition`` registration."""

from __future__ import annotations

from app.automations.triggers.store import register_trigger
from app.automations.triggers.types import TriggerDefinition

from .params import EventTriggerParams

EVENT_TRIGGER = TriggerDefinition(
    type="event",
    description="Fire when a matching domain event is published.",
    params_model=EventTriggerParams,
)

register_trigger(EVENT_TRIGGER)
