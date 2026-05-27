"""Built-in ``manual`` trigger. Self-registers at import time."""

from __future__ import annotations

from app.automations.schemas.triggers import ManualTriggerParams

from .store import register_trigger
from .types import TriggerDefinition

MANUAL_TRIGGER = TriggerDefinition(
    type="manual",
    description="Fire on a user-initiated 'Run now' invocation.",
    params_schema=ManualTriggerParams.model_json_schema(),
    payload_schema={"type": "object"},
)

register_trigger(MANUAL_TRIGGER)
