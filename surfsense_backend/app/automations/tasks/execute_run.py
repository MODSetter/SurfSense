"""Celery task that runs one automation. Thin wrapper over ``runtime.executor``."""

from __future__ import annotations

import logging

from app.automations.runtime import execute_run
from app.celery_app import celery_app
from app.tasks.celery_tasks import (
    get_celery_session_maker,
    run_async_celery_task,
)

logger = logging.getLogger(__name__)

TASK_NAME = "automation_run_execute"


@celery_app.task(name=TASK_NAME, bind=True)
def automation_run_execute(self, run_id: int) -> None:
    """Execute one ``AutomationRun``. Idempotent: terminal runs no-op."""
    return run_async_celery_task(lambda: _impl(run_id))


async def _impl(run_id: int) -> None:
    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        try:
            await execute_run(session, run_id)
        except Exception:
            logger.exception("automation_run %d failed unexpectedly", run_id)
            await session.rollback()
            raise
