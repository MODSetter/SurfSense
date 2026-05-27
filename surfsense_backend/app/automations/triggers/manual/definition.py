"""``manual`` ``TriggerDefinition`` registration."""

from __future__ import annotations

from ..store import register_trigger
from ..types import TriggerDefinition
from .params import ManualTriggerParams

MANUAL_TRIGGER = TriggerDefinition(
    type="manual",
    description="Fire on a user-initiated 'Run now' invocation.",
    params_model=ManualTriggerParams,
)

register_trigger(MANUAL_TRIGGER)
