"""Persistence operations on ``AutomationRun``. Pure SQL, no business logic."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.automations.persistence.enums.run_status import RunStatus
from app.automations.persistence.models.run import AutomationRun


async def load_run(session: AsyncSession, run_id: int) -> AutomationRun | None:
    """Load a run with its automation and trigger eagerly loaded."""
    stmt = (
        select(AutomationRun)
        .where(AutomationRun.id == run_id)
        .options(
            selectinload(AutomationRun.automation),
            selectinload(AutomationRun.trigger),
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def mark_running(session: AsyncSession, run: AutomationRun) -> None:
    run.status = RunStatus.RUNNING
    run.started_at = datetime.now(UTC)
    await session.flush()


async def mark_succeeded(session: AsyncSession, run: AutomationRun) -> None:
    run.status = RunStatus.SUCCEEDED
    run.finished_at = datetime.now(UTC)
    await session.flush()


async def mark_failed(
    session: AsyncSession,
    run: AutomationRun,
    error: dict[str, Any] | None,
) -> None:
    run.status = RunStatus.FAILED
    run.finished_at = datetime.now(UTC)
    run.error = error
    await session.flush()


async def append_step_result(
    session: AsyncSession,
    run: AutomationRun,
    step_result: dict[str, Any],
) -> None:
    """Append one step result. Reassigns the list so SQLAlchemy detects the change."""
    current = list(run.step_results or [])
    current.append(step_result)
    run.step_results = current
    await session.flush()
