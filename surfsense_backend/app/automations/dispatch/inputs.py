"""Merge and validate the inputs a run starts with."""

from __future__ import annotations

from typing import Any

import jsonschema

from app.automations.persistence.models.trigger import AutomationTrigger
from app.automations.schemas.definition.envelope import AutomationDefinition

from .errors import DispatchError


def prepare_inputs(
    definition: AutomationDefinition,
    trigger: AutomationTrigger,
    runtime_inputs: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge ``trigger.static_inputs`` over ``runtime_inputs``, then validate.

    Static inputs win on key collision.
    """
    merged = {**(runtime_inputs or {}), **(trigger.static_inputs or {})}
    return validate_inputs(definition, merged)


def validate_inputs(
    definition: AutomationDefinition, inputs: dict[str, Any]
) -> dict[str, Any]:
    """Validate ``inputs`` against the definition's optional declared schema.

    No declared schema → pass through unchanged so runtime keys (``fired_at``,
    ``last_fired_at``, ...) still reach the template context. A declared schema
    that the inputs violate is surfaced as ``DispatchError``.
    """
    if definition.inputs is None or not definition.inputs.schema_:
        return inputs
    try:
        jsonschema.validate(instance=inputs, schema=definition.inputs.schema_)
    except jsonschema.ValidationError as exc:
        raise DispatchError(f"inputs: {exc.message}") from exc
    return inputs
