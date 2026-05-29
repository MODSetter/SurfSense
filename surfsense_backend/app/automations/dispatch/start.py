"""Start one run for a trigger: resolve its automation, guard ``ACTIVE``, dispatch.

Shared by every trigger type. A type's selector builds the runtime inputs and
hands one trigger row here; this resolves and guards the automation, then calls
the generic ``dispatch_run``.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.automations.persistence.enums.automation_status import AutomationStatus
from app.automations.persistence.models.automation import Automation
from app.automations.persistence.models.run import AutomationRun
from app.automations.persistence.models.trigger import AutomationTrigger

from .errors import DispatchError
from .run import dispatch_run


async def start_run(
    *,
    session: AsyncSession,
    trigger: AutomationTrigger,
    runtime_inputs: dict[str, Any] | None = None,
) -> AutomationRun:
    """Resolve ``trigger``'s automation, require it ``ACTIVE``, dispatch a run."""
    automation = await _load_automation(session, trigger.automation_id)
    if automation is None:
        raise DispatchError(
            f"automation {trigger.automation_id} not found for trigger {trigger.id}"
        )

    if automation.status != AutomationStatus.ACTIVE:
        raise DispatchError(
            f"automation {trigger.automation_id} is {automation.status.value}, not active"
        )

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
