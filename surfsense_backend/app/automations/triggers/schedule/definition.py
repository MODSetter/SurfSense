"""``schedule`` ``TriggerDefinition`` registration."""

from __future__ import annotations

from ..store import register_trigger
from ..types import TriggerDefinition
from .params import ScheduleTriggerParams

SCHEDULE_TRIGGER = TriggerDefinition(
    type="schedule",
    description="Fire on a cron schedule in a given timezone.",
    params_model=ScheduleTriggerParams,
)

register_trigger(SCHEDULE_TRIGGER)
