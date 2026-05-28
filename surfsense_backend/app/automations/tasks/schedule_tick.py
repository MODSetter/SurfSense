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
from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class _Claim:
    """Per-trigger fire context captured before row state is mutated."""

    trigger_id: int
    scheduled_for: datetime
    previous_last_fired_at: datetime | None


@celery_app.task(name=TASK_NAME)
def automation_schedule_tick() -> None:
    """Tick once: self-heal NULL next_fire_at, claim due rows, fire each."""
    return run_async_celery_task(_tick)


async def _tick() -> None:
    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        now = datetime.now(UTC)

        await _self_heal_null_next_fire(session, now=now)

        claims = await _claim_due_triggers(session, now=now)
        if not claims:
            return

        for claim in claims:
            await _fire_one(session, claim=claim, fired_at=now)


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
) -> list[_Claim]:
    """Lock and advance due rows; return per-trigger fire context."""
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

    claims: list[_Claim] = []
    for trigger in triggers:
        # Snapshot fire-context BEFORE we advance the row.
        scheduled_for = trigger.next_fire_at
        previous_last_fired_at = trigger.last_fired_at

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
        claims.append(
            _Claim(
                trigger_id=trigger.id,
                scheduled_for=scheduled_for,
                previous_last_fired_at=previous_last_fired_at,
            )
        )

    await session.commit()
    return claims


async def _fire_one(
    session: AsyncSession, *, claim: _Claim, fired_at: datetime
) -> None:
    """Reload the trigger post-commit and dispatch a run for it."""
    trigger = await session.get(AutomationTrigger, claim.trigger_id)
    if trigger is None:
        return

    try:
        run = await dispatch_schedule_run(
            session=session,
            trigger=trigger,
            fired_at=fired_at,
            scheduled_for=claim.scheduled_for,
            previous_last_fired_at=claim.previous_last_fired_at,
        )
        logger.info(
            "scheduled fire: trigger=%d automation=%d run=%d",
            claim.trigger_id,
            trigger.automation_id,
            run.id,
        )
    except Exception:
        logger.exception(
            "scheduled fire failed for trigger %d (next attempt at next match)",
            claim.trigger_id,
        )
        await session.rollback()
