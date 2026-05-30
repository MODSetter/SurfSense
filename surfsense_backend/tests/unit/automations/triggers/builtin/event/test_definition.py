"""The ``event`` trigger self-registers on the triggers store at import."""

from __future__ import annotations

import pytest

from app.automations.triggers import get_trigger
from app.automations.triggers.builtin.event.params import EventTriggerParams

pytestmark = pytest.mark.unit


def test_event_trigger_is_registered() -> None:
    definition = get_trigger("event")

    assert definition is not None
    assert definition.type == "event"
    assert definition.params_model is EventTriggerParams
