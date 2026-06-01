"""Event selector (worker task): pick the triggers an event fires, start each.

The source enqueues this with a serialized event. Here we load the enabled
``event`` triggers for that event type, keep the ones whose filter matches the
payload, and start a run for each. Per-trigger failures are isolated.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.automations.dispatch import launch_run
from app.automations.persistence.enums.trigger_type import TriggerType
from app.automations.persistence.models.trigger import AutomationTrigger
from app.celery_app import celery_app
from app.event_bus import Event
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

from .inputs import event_runtime_inputs
from .match import trigger_matches_event
from .source import TASK_NAME

logger = logging.getLogger(__name__)


@celery_app.task(name=TASK_NAME)
def automation_event_select(event: dict[str, Any]) -> None:
    """Select and start the runs an event fires."""
    return run_async_celery_task(lambda: _select_and_start(event))


async def _select_and_start(event_dict: dict[str, Any]) -> None:
    event = Event.model_validate(event_dict)
    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        for trigger in await _eligible(session, event=event):
            await _start_one(session, trigger=trigger, event=event)


async def _eligible(session: AsyncSession, *, event: Event) -> list[AutomationTrigger]:
    """Enabled ``event`` triggers for this event type whose filter matches."""
    stmt = select(AutomationTrigger).where(
        AutomationTrigger.type == TriggerType.EVENT,
        AutomationTrigger.enabled.is_(True),
        AutomationTrigger.params["event_type"].astext == event.event_type,
    )
    triggers = (await session.execute(stmt)).scalars().all()
    return [t for t in triggers if trigger_matches_event(t.params, event)]


async def _start_one(
    session: AsyncSession, *, trigger: AutomationTrigger, event: Event
) -> None:
    try:
        run = await launch_run(
            session=session,
            trigger=trigger,
            runtime_inputs=event_runtime_inputs(event),
        )
        logger.info(
            "event fire: trigger=%d automation=%d run=%d event=%s",
            trigger.id,
            trigger.automation_id,
            run.id,
            event.event_id,
        )
    except Exception:
        logger.exception("event fire failed for trigger %d", trigger.id)
        await session.rollback()
