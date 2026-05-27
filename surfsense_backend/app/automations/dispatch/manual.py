"""Manual ``Run now`` dispatch: validate inputs, snapshot the definition, enqueue."""

from __future__ import annotations

from typing import Any

import jsonschema
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.automations.persistence.enums.automation_status import AutomationStatus
from app.automations.persistence.enums.run_status import RunStatus
from app.automations.persistence.enums.trigger_type import TriggerType
from app.automations.persistence.models.automation import Automation
from app.automations.persistence.models.run import AutomationRun
from app.automations.persistence.models.trigger import AutomationTrigger
from app.automations.schemas.definition.envelope import AutomationDefinition
from app.automations.tasks.execute_run import automation_run_execute


class DispatchError(Exception):
    """A manual dispatch could not proceed (missing trigger, invalid inputs, ...)."""


async def dispatch_manual_run(
    *,
    session: AsyncSession,
    automation_id: int,
    payload: dict[str, Any] | None,
) -> AutomationRun:
    """Validate, snapshot, persist, and enqueue an ``AutomationRun``."""
    automation = await _load_automation(session, automation_id)
    if automation is None:
        raise DispatchError(f"automation {automation_id} not found")

    if automation.status != AutomationStatus.ACTIVE:
        raise DispatchError(
            f"automation {automation_id} is {automation.status.value}, not active"
        )

    try:
        definition = AutomationDefinition.model_validate(automation.definition)
    except Exception as exc:
        raise DispatchError(f"invalid automation definition: {exc}") from exc

    trigger = await _find_manual_trigger(session, automation_id)
    if trigger is None:
        raise DispatchError(
            f"automation {automation_id} has no enabled manual trigger"
        )

    resolved_inputs = _validate_inputs(definition, payload or {})
    snapshot = definition.model_dump(mode="json", by_alias=True)

    run = AutomationRun(
        automation_id=automation_id,
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


async def _load_automation(
    session: AsyncSession, automation_id: int
) -> Automation | None:
    stmt = select(Automation).where(Automation.id == automation_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def _find_manual_trigger(
    session: AsyncSession, automation_id: int
) -> AutomationTrigger | None:
    stmt = (
        select(AutomationTrigger)
        .where(
            AutomationTrigger.automation_id == automation_id,
            AutomationTrigger.type == TriggerType.MANUAL,
            AutomationTrigger.enabled.is_(True),
        )
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


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
