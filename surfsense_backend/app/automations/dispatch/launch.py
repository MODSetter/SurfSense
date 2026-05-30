"""Launch a run for a trigger that fired: resolve, validate, persist, enqueue.

The trigger-facing entry every selector calls. A selector builds the runtime
inputs and hands one trigger row here; this resolves and guards its automation,
snapshots the definition onto a PENDING run, and enqueues execution. The
snapshot makes the run immune to later edits of the automation.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.automations.persistence.enums.run_status import RunStatus
from app.automations.persistence.models.run import AutomationRun
from app.automations.persistence.models.trigger import AutomationTrigger
from app.automations.schemas.definition.envelope import AutomationDefinition
from app.automations.tasks.execute_run import automation_run_execute

from .errors import DispatchError
from .inputs import prepare_inputs
from .resolve import resolve_active_automation


async def launch_run(
    *,
    session: AsyncSession,
    trigger: AutomationTrigger,
    runtime_inputs: dict[str, Any] | None = None,
) -> AutomationRun:
    """Resolve ``trigger``'s active automation and enqueue a PENDING run for it."""
    automation = await resolve_active_automation(session, trigger)

    try:
        definition = AutomationDefinition.model_validate(automation.definition)
    except Exception as exc:
        raise DispatchError(f"invalid automation definition: {exc}") from exc

    inputs = prepare_inputs(definition, trigger, runtime_inputs)
    snapshot = definition.model_dump(mode="json", by_alias=True)

    run = AutomationRun(
        automation_id=automation.id,
        trigger_id=trigger.id,
        status=RunStatus.PENDING,
        definition_snapshot=snapshot,
        inputs=inputs,
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
