"""Celery Beat tick that fires due ``schedule`` triggers.

Runs every minute. Each tick performs two passes:

1. **Self-heal**: enabled schedule triggers with NULL ``next_fire_at`` get
   it computed from their ``cron`` + ``timezone`` (e.g. fresh inserts or
   rows restored from backup).
2. **Claim & fire**: due rows are locked with ``FOR UPDATE SKIP LOCKED``,
   their ``next_fire_at`` is advanced and ``last_fired_at`` is set, and
   ``dispatch_schedule_run`` is invoked for each. Dispatch errors are
   logged; a missed fire stays missed (matches K8s CronJob / Airflow
   ``catchup=False`` semantics).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.automations.persistence.enums.trigger_type import TriggerType
from app.automations.persistence.models.trigger import AutomationTrigger
from app.automations.triggers.schedule import (
    InvalidCronError,
    compute_next_fire_at,
    dispatch_schedule_run,
)
from app.celery_app import celery_app
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

logger = logging.getLogger(__name__)

TASK_NAME = "automation_schedule_tick"

# Cap rows touched per tick so a backlog of due triggers can't starve the
# worker; remaining rows fire on the next tick.
_TICK_BATCH = 200


@celery_app.task(name=TASK_NAME)
def automation_schedule_tick() -> None:
    """Tick once: self-heal NULL next_fire_at, claim due rows, fire each."""
    return run_async_celery_task(_tick)


async def _tick() -> None:
    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        now = datetime.now(UTC)

        await _self_heal_null_next_fire(session, now=now)

        claimed_ids = await _claim_due_triggers(session, now=now)
        if not claimed_ids:
            return

        for trigger_id in claimed_ids:
            await _fire_one(session, trigger_id=trigger_id)


async def _self_heal_null_next_fire(session: AsyncSession, *, now: datetime) -> None:
    """Backfill ``next_fire_at`` for enabled schedule triggers missing it."""
    stmt = (
        select(AutomationTrigger)
        .where(
            AutomationTrigger.type == TriggerType.SCHEDULE,
            AutomationTrigger.enabled.is_(True),
            AutomationTrigger.next_fire_at.is_(None),
        )
        .limit(_TICK_BATCH)
    )
    triggers = (await session.execute(stmt)).scalars().all()
    if not triggers:
        return

    for trigger in triggers:
        try:
            trigger.next_fire_at = compute_next_fire_at(
                trigger.params["cron"],
                trigger.params["timezone"],
                after=now,
            )
        except (InvalidCronError, KeyError, TypeError) as exc:
            logger.warning(
                "automation_trigger %d has invalid schedule params, disabling: %s",
                trigger.id,
                exc,
            )
            trigger.enabled = False

    await session.commit()


async def _claim_due_triggers(
    session: AsyncSession, *, now: datetime
) -> list[int]:
    """Lock and advance due rows; return claimed trigger ids."""
    stmt = (
        select(AutomationTrigger)
        .where(
            AutomationTrigger.type == TriggerType.SCHEDULE,
            AutomationTrigger.enabled.is_(True),
            AutomationTrigger.next_fire_at.isnot(None),
            AutomationTrigger.next_fire_at <= now,
        )
        .order_by(AutomationTrigger.next_fire_at)
        .limit(_TICK_BATCH)
        .with_for_update(skip_locked=True)
    )
    triggers = (await session.execute(stmt)).scalars().all()
    if not triggers:
        return []

    claimed: list[int] = []
    for trigger in triggers:
        try:
            trigger.next_fire_at = compute_next_fire_at(
                trigger.params["cron"],
                trigger.params["timezone"],
                after=now,
            )
        except (InvalidCronError, KeyError, TypeError) as exc:
            logger.warning(
                "automation_trigger %d has invalid schedule params, disabling: %s",
                trigger.id,
                exc,
            )
            trigger.enabled = False
            continue

        trigger.last_fired_at = now
        claimed.append(trigger.id)

    await session.commit()
    return claimed


async def _fire_one(session: AsyncSession, *, trigger_id: int) -> None:
    """Reload the trigger post-commit and dispatch a run for it."""
    trigger = await session.get(AutomationTrigger, trigger_id)
    if trigger is None:
        return

    try:
        run = await dispatch_schedule_run(session=session, trigger=trigger)
        logger.info(
            "scheduled fire: trigger=%d automation=%d run=%d",
            trigger_id,
            trigger.automation_id,
            run.id,
        )
    except Exception:
        logger.exception(
            "scheduled fire failed for trigger %d (next attempt at next match)",
            trigger_id,
        )
        await session.rollback()
