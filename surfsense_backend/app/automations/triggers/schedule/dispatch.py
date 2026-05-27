"""Schedule dispatch adapter: load + guard, then call generic dispatch."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.automations.dispatch import DispatchError, dispatch_run
from app.automations.persistence.enums.automation_status import AutomationStatus
from app.automations.persistence.models.automation import Automation
from app.automations.persistence.models.run import AutomationRun
from app.automations.persistence.models.trigger import AutomationTrigger


async def dispatch_schedule_run(
    *,
    session: AsyncSession,
    trigger: AutomationTrigger,
    fired_at: datetime,
    scheduled_for: datetime,
    previous_last_fired_at: datetime | None,
) -> AutomationRun:
    """Fire one scheduled run for ``trigger``.

    Emits calendar context as runtime inputs:

    - ``fired_at`` — actual fire time
    - ``scheduled_for`` — cron-derived target time for this fire
    - ``last_fired_at`` — fire time of the previous run, or null on first fire

    The caller (the schedule tick) is responsible for selecting due triggers
    and advancing ``next_fire_at`` / ``last_fired_at`` before invoking this.
    """
    automation = await _load_automation(session, trigger.automation_id)
    if automation is None:
        raise DispatchError(
            f"automation {trigger.automation_id} not found for trigger {trigger.id}"
        )

    if automation.status != AutomationStatus.ACTIVE:
        raise DispatchError(
            f"automation {trigger.automation_id} is {automation.status.value}, not active"
        )

    runtime_inputs = {
        "fired_at": fired_at.isoformat(),
        "scheduled_for": scheduled_for.isoformat(),
        "last_fired_at": (
            previous_last_fired_at.isoformat() if previous_last_fired_at else None
        ),
    }

    return await dispatch_run(
        session=session,
        automation=automation,
        trigger=trigger,
        runtime_inputs=runtime_inputs,
    )


async def _load_automation(
    session: AsyncSession, automation_id: int
) -> Automation | None:
    stmt = select(Automation).where(Automation.id == automation_id)
    return (await session.execute(stmt)).scalar_one_or_none()
