"""Lock the ``TriggerSpec`` validation contract — the entry shape used
inside an automation's ``triggers[]`` array.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.automations.schemas.definition.trigger_spec import TriggerSpec

pytestmark = pytest.mark.unit


def test_trigger_spec_accepts_type_with_default_empty_params() -> None:
    """``type`` is required; ``params`` defaults to ``{}`` so triggers
    that take no params don't need an explicit body."""
    spec = TriggerSpec(type="schedule")

    assert spec.type == "schedule"
    assert spec.params == {}


def test_trigger_spec_rejects_empty_type() -> None:
    """``type`` is the registry lookup key — empty would silently miss."""
    with pytest.raises(ValidationError):
        TriggerSpec(type="")


def test_trigger_spec_rejects_unknown_field() -> None:
    """``extra='forbid'`` catches typos at definition-validation time."""
    with pytest.raises(ValidationError):
        TriggerSpec.model_validate({"type": "schedule", "paramz": {}})
