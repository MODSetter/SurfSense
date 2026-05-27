"""Built-in ``schedule`` trigger. Self-registers at import time."""

from __future__ import annotations

from app.automations.schemas.triggers import ScheduleTriggerParams

from .store import register_trigger
from .types import TriggerDefinition

SCHEDULE_TRIGGER = TriggerDefinition(
    type="schedule",
    description="Fire on a cron schedule in a given timezone.",
    params_schema=ScheduleTriggerParams.model_json_schema(),
    payload_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {},
    },
)

register_trigger(SCHEDULE_TRIGGER)
