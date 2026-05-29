"""Lock the input-validation contract enforced before a run is enqueued.

``validate_inputs`` is the pure schema check that ``enqueue_run`` runs against
merged inputs. ``enqueue_run`` itself needs a real DB session, so tests target
this pure function directly; the contract — not the symbol — is what's locked.
"""

from __future__ import annotations

import pytest

from app.automations.dispatch.errors import DispatchError
from app.automations.dispatch.inputs import validate_inputs
from app.automations.schemas.definition.envelope import AutomationDefinition
from app.automations.schemas.definition.inputs import Inputs
from app.automations.schemas.definition.plan_step import PlanStep

pytestmark = pytest.mark.unit


def _minimal_definition(*, inputs: Inputs | None = None) -> AutomationDefinition:
    """One-step definition with an optional declared input schema."""
    return AutomationDefinition(
        name="test",
        inputs=inputs,
        plan=[PlanStep(step_id="s1", action="agent_task")],
    )


def test_validate_inputs_passes_through_when_no_schema_is_declared() -> None:
    """When the definition declares no input schema, runtime inputs reach
    the template context **unchanged**. Regression site: previously this
    branch returned ``{}``, which stripped runtime keys like ``fired_at``
    and ``last_fired_at`` and made Jinja blow up on ``{{ inputs.* }}``.
    """
    definition = _minimal_definition(inputs=None)
    runtime_inputs = {
        "fired_at": "2026-01-01T00:00:00+00:00",
        "last_fired_at": None,
        "static_key": "value",
    }

    assert validate_inputs(definition, runtime_inputs) == runtime_inputs


def test_validate_inputs_returns_inputs_when_they_match_declared_schema() -> None:
    """With a declared JSON schema, inputs that satisfy it pass through
    unchanged (validation succeeds; the function does not coerce or
    strip extra fields not mentioned in the schema)."""
    schema = {
        "type": "object",
        "properties": {"topic": {"type": "string"}},
        "required": ["topic"],
    }
    definition = _minimal_definition(inputs=Inputs(schema=schema))

    inputs = {"topic": "weekly report"}

    assert validate_inputs(definition, inputs) == inputs


def test_validate_inputs_raises_dispatch_error_when_inputs_violate_schema() -> None:
    """Inputs that don't match the declared schema must surface as
    ``DispatchError`` (not the raw ``jsonschema.ValidationError``), so every
    caller can handle one dispatch-domain exception type uniformly."""
    schema = {
        "type": "object",
        "properties": {"topic": {"type": "string"}},
        "required": ["topic"],
    }
    definition = _minimal_definition(inputs=Inputs(schema=schema))

    with pytest.raises(DispatchError):
        validate_inputs(definition, {"topic": 42})  # type violates string
