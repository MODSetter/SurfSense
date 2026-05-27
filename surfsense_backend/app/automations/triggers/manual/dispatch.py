"""Manual ``Run now`` dispatch adapter: load + guard, then call generic dispatch."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.automations.dispatch import DispatchError, dispatch_run
from app.automations.persistence.enums.automation_status import AutomationStatus
from app.automations.persistence.enums.trigger_type import TriggerType
from app.automations.persistence.models.automation import Automation
from app.automations.persistence.models.run import AutomationRun
from app.automations.persistence.models.trigger import AutomationTrigger


async def dispatch_manual_run(
    *,
    session: AsyncSession,
    automation_id: int,
    payload: dict[str, Any] | None,
) -> AutomationRun:
    """Find the automation + its enabled manual trigger, then run the generic dispatch."""
    automation = await _load_automation(session, automation_id)
    if automation is None:
        raise DispatchError(f"automation {automation_id} not found")

    if automation.status != AutomationStatus.ACTIVE:
        raise DispatchError(
            f"automation {automation_id} is {automation.status.value}, not active"
        )

    trigger = await _find_manual_trigger(session, automation_id)
    if trigger is None:
        raise DispatchError(
            f"automation {automation_id} has no enabled manual trigger"
        )

    return await dispatch_run(
        session=session,
        automation=automation,
        trigger=trigger,
        payload=payload,
    )


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
