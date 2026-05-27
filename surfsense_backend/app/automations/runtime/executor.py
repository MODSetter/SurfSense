"""Walk an ``AutomationRun``'s snapshot plan to terminal state."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.automations.persistence.enums.run_status import RunStatus
from app.automations.persistence.models.run import AutomationRun
from app.automations.actions.types import ActionContext
from app.automations.schemas.definition.envelope import AutomationDefinition
from app.automations.schemas.definition.plan_step import PlanStep
from app.automations.templating import build_run_context

from . import repository
from .step import execute_step


async def execute_run(session: AsyncSession, run_id: int) -> None:
    """Load run ``run_id`` and execute its snapshot plan to a terminal state."""
    run = await repository.load_run(session, run_id)
    if run is None:
        raise ValueError(f"automation_run {run_id} not found")

    if run.status != RunStatus.PENDING:
        return

    try:
        definition = AutomationDefinition.model_validate(run.definition_snapshot)
    except Exception as exc:
        await repository.mark_failed(
            session,
            run,
            {"message": f"definition_snapshot invalid: {exc}", "type": type(exc).__name__},
        )
        await session.commit()
        return

    await repository.mark_running(session, run)
    await session.commit()

    step_outputs: dict[str, Any] = {}

    for step in definition.plan:
        template_ctx = _build_template_ctx(run, step_outputs)
        action_ctx = _build_action_ctx(session, run, step)
        result = await execute_step(
            step=step,
            template_context=template_ctx,
            action_context=action_ctx,
            default_max_retries=definition.execution.max_retries,
            default_retry_backoff=definition.execution.retry_backoff,
            default_timeout_seconds=definition.execution.timeout_seconds,
        )
        await repository.append_step_result(session, run, result)
        await session.commit()

        if result["status"] == "failed":
            await _run_on_failure(session, run, definition)
            await repository.mark_failed(session, run, result.get("error"))
            await session.commit()
            return

        if result["status"] == "succeeded":
            step_outputs[step.output_as or step.step_id] = result.get("result")

    await repository.mark_succeeded(session, run)
    await session.commit()


async def _run_on_failure(
    session: AsyncSession,
    run: AutomationRun,
    definition: AutomationDefinition,
) -> None:
    """Run the on_failure steps. Their failures don't recurse into more on_failure."""
    if not definition.execution.on_failure:
        return
    template_ctx = _build_template_ctx(run, step_outputs={})
    for step in definition.execution.on_failure:
        action_ctx = _build_action_ctx(session, run, step)
        result = await execute_step(
            step=step,
            template_context=template_ctx,
            action_context=action_ctx,
            default_max_retries=definition.execution.max_retries,
            default_retry_backoff=definition.execution.retry_backoff,
            default_timeout_seconds=definition.execution.timeout_seconds,
        )
        await repository.append_step_result(session, run, result)
        await session.commit()


def _build_template_ctx(run: AutomationRun, step_outputs: dict[str, Any]) -> dict[str, Any]:
    automation = run.automation
    trigger = run.trigger
    return build_run_context(
        run_id=run.id,
        automation_id=run.automation_id,
        automation_name=automation.name if automation else None,
        automation_version=automation.version if automation else None,
        search_space_id=automation.search_space_id if automation else None,
        creator_id=automation.created_by_user_id if automation else None,
        trigger_id=run.trigger_id,
        trigger_type=trigger.type.value if trigger else None,
        started_at=run.started_at,
        attempt=1,
        inputs=run.inputs or {},
        step_outputs=step_outputs,
    )


def _build_action_ctx(
    session: AsyncSession, run: AutomationRun, step: PlanStep
) -> ActionContext:
    automation = run.automation
    return ActionContext(
        session=session,
        run_id=run.id,
        step_id=step.step_id,
        search_space_id=automation.search_space_id,
        creator_user_id=automation.created_by_user_id,
    )
