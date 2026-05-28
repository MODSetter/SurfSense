"""Lock the ``params_schema`` derivation on action + trigger definitions.

Both definition dataclasses expose ``params_schema`` as the JSON Schema
of their ``params_model``. This is what the registry endpoints surface
to the UI as the "what shape do these params take?" contract.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from app.automations.actions.types import ActionDefinition
from app.automations.triggers.types import TriggerDefinition

pytestmark = pytest.mark.unit


class _Topic(BaseModel):
    """Model with one required string field — minimal schema fingerprint."""

    topic: str


def test_action_definition_params_schema_reflects_params_model() -> None:
    """``ActionDefinition.params_schema`` returns a JSON Schema derived
    from the Pydantic ``params_model`` — required fields and types are
    visible to clients consuming the registry endpoint."""
    definition = ActionDefinition(
        type="t",
        name="N",
        description="D",
        params_model=_Topic,
        build_handler=lambda _ctx: (lambda _p: {}),  # type: ignore[arg-type,return-value]
    )

    schema = definition.params_schema

    assert schema["type"] == "object"
    assert schema["properties"]["topic"]["type"] == "string"
    assert "topic" in schema["required"]


def test_trigger_definition_params_schema_reflects_params_model() -> None:
    """Same JSON-Schema derivation contract on the trigger side."""
    definition = TriggerDefinition(
        type="t",
        description="D",
        params_model=_Topic,
    )

    schema = definition.params_schema

    assert schema["type"] == "object"
    assert schema["properties"]["topic"]["type"] == "string"
    assert "topic" in schema["required"]
