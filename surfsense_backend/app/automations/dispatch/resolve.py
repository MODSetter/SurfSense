"""Resolve the automation behind a trigger and guard that it may run."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.automations.persistence.enums.automation_status import AutomationStatus
from app.automations.persistence.models.automation import Automation
from app.automations.persistence.models.trigger import AutomationTrigger

from .errors import DispatchError


async def resolve_active_automation(
    session: AsyncSession, trigger: AutomationTrigger
) -> Automation:
    """Load ``trigger``'s automation and require it ``ACTIVE``.

    Raises ``DispatchError`` if the automation is missing or not active.
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

    return automation


async def _load_automation(
    session: AsyncSession, automation_id: int
) -> Automation | None:
    stmt = select(Automation).where(Automation.id == automation_id)
    return (await session.execute(stmt)).scalar_one_or_none()
