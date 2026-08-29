"""Broker publication seam for queued deliverable jobs."""

from __future__ import annotations

from typing import Protocol

DELIVERABLE_JOB_TASK = "deliverables.execute_queued"


class DeliverableJobDispatcher(Protocol):
    def __call__(
        self,
        *,
        job_id: int,
        task_id: str,
    ) -> None: ...


def dispatch_deliverable_job(
    *,
    job_id: int,
    task_id: str,
) -> None:
    """Publish one job without importing Celery during tool construction."""
    from app.celery_app import celery_app

    celery_app.send_task(
        DELIVERABLE_JOB_TASK,
        kwargs={"job_id": job_id},
        task_id=task_id,
    )
