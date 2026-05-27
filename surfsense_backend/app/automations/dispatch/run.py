"""Generic run dispatch: validate, snapshot, persist, enqueue. Shared by every trigger."""

from __future__ import annotations

from typing import Any

import jsonschema
from sqlalchemy.ext.asyncio import AsyncSession

from app.automations.persistence.enums.run_status import RunStatus
from app.automations.persistence.models.automation import Automation
from app.automations.persistence.models.run import AutomationRun
from app.automations.persistence.models.trigger import AutomationTrigger
from app.automations.schemas.definition.envelope import AutomationDefinition
from app.automations.tasks.execute_run import automation_run_execute

from .errors import DispatchError


async def dispatch_run(
    *,
    session: AsyncSession,
    automation: Automation,
    trigger: AutomationTrigger,
    payload: dict[str, Any] | None,
) -> AutomationRun:
    """Validate, snapshot the definition, persist an ``AutomationRun``, enqueue execution.

    Callers (trigger-specific adapters) are responsible for resolving
    ``automation`` and ``trigger`` and for the trigger-side ``ACTIVE`` /
    ``enabled`` guards. This function only handles what's identical across
    every trigger type.
    """
    try:
        definition = AutomationDefinition.model_validate(automation.definition)
    except Exception as exc:
        raise DispatchError(f"invalid automation definition: {exc}") from exc

    resolved_inputs = _validate_inputs(definition, payload or {})
    snapshot = definition.model_dump(mode="json", by_alias=True)

    run = AutomationRun(
        automation_id=automation.id,
        trigger_id=trigger.id,
        status=RunStatus.PENDING,
        definition_snapshot=snapshot,
        trigger_payload=payload,
        resolved_inputs=resolved_inputs,
        step_results=[],
        artifacts=[],
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    automation_run_execute.apply_async(
        args=[run.id],
        time_limit=definition.execution.timeout_seconds,
    )
    return run


def _validate_inputs(
    definition: AutomationDefinition, payload: dict[str, Any]
) -> dict[str, Any]:
    if definition.inputs is None or not definition.inputs.schema_:
        return {}
    try:
        jsonschema.validate(instance=payload, schema=definition.inputs.schema_)
    except jsonschema.ValidationError as exc:
        raise DispatchError(f"inputs: {exc.message}") from exc
    return payload
