"""Lock the request-side trigger API schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.automations.persistence.enums.trigger_type import TriggerType
from app.automations.schemas.api.trigger import TriggerCreate, TriggerUpdate

pytestmark = pytest.mark.unit


def test_trigger_create_uses_safe_defaults_for_optional_fields() -> None:
    """Defaults: empty ``params`` and ``static_inputs``, ``enabled=True``.
    These let callers create a trigger with just ``type`` + the params
    the trigger requires."""
    trigger = TriggerCreate(type=TriggerType.SCHEDULE)  # type: ignore[arg-type]

    assert trigger.type is TriggerType.SCHEDULE
    assert trigger.params == {}
    assert trigger.static_inputs == {}
    assert trigger.enabled is True


def test_trigger_create_rejects_unknown_trigger_type_string() -> None:
    """``type`` is a ``TriggerType`` enum, so any string outside the
    enum's known values fails validation at the boundary."""
    with pytest.raises(ValidationError):
        TriggerCreate.model_validate({"type": "webhook"})  # not in TriggerType


def test_trigger_create_rejects_unknown_field() -> None:
    """``extra='forbid'`` catches typos in trigger payloads."""
    with pytest.raises(ValidationError):
        TriggerCreate.model_validate(
            {"type": "schedule", "param": {}}  # typo: param vs params
        )


def test_trigger_update_accepts_partial_payload_with_no_fields() -> None:
    """``TriggerUpdate`` is fully optional — empty body is valid (no-op)."""
    update = TriggerUpdate()

    assert update.enabled is None
    assert update.params is None
    assert update.static_inputs is None
