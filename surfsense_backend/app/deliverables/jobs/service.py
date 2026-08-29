"""Small transactional API for the deliverable-job state machine."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    DeliverableFailureCode,
    DeliverableJob,
    DeliverableJobStatus,
)
from app.deliverables.jobs.policy import get_deliverable_kind_spec

_MAX_INTERNAL_ERROR_LENGTH = 2000


def task_id_for_attempt(job_id: int, attempt_count: int) -> str:
    if job_id <= 0 or attempt_count <= 0:
        raise ValueError("job id and attempt count must be positive")
    return f"deliverable-job:{job_id}:attempt:{attempt_count}"


async def create_deliverable_job(
    session: AsyncSession,
    *,
    kind: str,
    title: str,
    workspace_id: int,
    tool_call_id: str,
    request: Mapping[str, Any],
    thread_id: int | None = None,
    created_by_id: UUID | None = None,
) -> tuple[DeliverableJob, bool]:
    """Create one job or return the row for the same tool invocation.

    The PostgreSQL conflict clause makes concurrent retries idempotent without
    poisoning the transaction. The caller owns the commit and must commit
    before publishing to Celery.
    """

    get_deliverable_kind_spec(kind)
    if not title.strip() or not tool_call_id:
        raise ValueError("title and tool_call_id are required")

    insert_result = await session.execute(
        pg_insert(DeliverableJob)
        .values(
            kind=kind,
            title=title.strip(),
            workspace_id=workspace_id,
            thread_id=thread_id,
            created_by_id=created_by_id,
            tool_call_id=tool_call_id,
            request=dict(request),
            checkpoint={},
        )
        .on_conflict_do_nothing(
            constraint="uq_deliverable_jobs_workspace_kind_tool_call"
        )
        .returning(DeliverableJob.id)
    )
    inserted_id = insert_result.scalar_one_or_none()
    created = inserted_id is not None

    if created:
        task_id = task_id_for_attempt(inserted_id, 1)
        await session.execute(
            update(DeliverableJob)
            .where(DeliverableJob.id == inserted_id)
            .values(celery_task_id=task_id, updated_at=_now())
        )

    result = await session.execute(
        select(DeliverableJob).where(
            DeliverableJob.workspace_id == workspace_id,
            DeliverableJob.kind == kind,
            DeliverableJob.tool_call_id == tool_call_id,
        )
    )
    return result.scalar_one(), created


async def claim_deliverable_job(
    session: AsyncSession,
    job_id: int,
    *,
    task_id: str | None = None,
    attempt_count: int | None = None,
) -> DeliverableJob | None:
    """Atomically claim a queued attempt; duplicate deliveries return ``None``."""

    conditions = [
        DeliverableJob.id == job_id,
        DeliverableJob.status == DeliverableJobStatus.QUEUED,
        DeliverableJob.artifact_id.is_(None),
    ]
    if task_id is not None:
        conditions.append(DeliverableJob.celery_task_id == task_id)
    if attempt_count is not None:
        conditions.append(DeliverableJob.attempt_count == attempt_count)

    now = _now()
    return await _transition(
        session,
        conditions,
        status=DeliverableJobStatus.RUNNING,
        phase="starting",
        claimed_at=now,
        heartbeat_at=now,
        failure_code=None,
        internal_error=None,
    )


async def requeue_claimed_deliverable_job(
    session: AsyncSession,
    job_id: int,
    *,
    task_id: str | None,
    internal_error: str | None = None,
) -> DeliverableJob | None:
    """Release a claim only so Celery can retry the same deterministic attempt."""
    conditions = [
        DeliverableJob.id == job_id,
        DeliverableJob.status == DeliverableJobStatus.RUNNING,
        DeliverableJob.artifact_id.is_(None),
    ]
    if task_id is not None:
        conditions.append(DeliverableJob.celery_task_id == task_id)
    return await _transition(
        session,
        conditions,
        status=DeliverableJobStatus.QUEUED,
        phase=None,
        progress=0,
        internal_error=_bounded_error(internal_error),
        claimed_at=None,
        heartbeat_at=None,
        finished_at=None,
    )


async def heartbeat_deliverable_job(
    session: AsyncSession,
    job_id: int,
    *,
    phase: str,
    progress: int,
    checkpoint: Mapping[str, Any] | None = None,
    task_id: str | None = None,
) -> DeliverableJob | None:
    phase = phase.strip()
    if not phase or len(phase) > 64:
        raise ValueError("phase must be between 1 and 64 characters")
    if not 0 <= progress < 100:
        raise ValueError("running progress must be between 0 and 99")
    values: dict[str, Any] = {
        "phase": phase,
        "progress": progress,
        "heartbeat_at": _now(),
    }
    if checkpoint is not None:
        values["checkpoint"] = dict(checkpoint)
    conditions = [
        DeliverableJob.id == job_id,
        DeliverableJob.status == DeliverableJobStatus.RUNNING,
    ]
    if task_id is not None:
        conditions.append(DeliverableJob.celery_task_id == task_id)
    return await _transition(session, conditions, **values)


async def complete_deliverable_job(
    session: AsyncSession,
    job_id: int,
    *,
    artifact_id: int,
    task_id: str | None = None,
) -> DeliverableJob | None:
    if artifact_id <= 0:
        raise ValueError("ready jobs require an artifact")
    now = _now()
    conditions = [
        DeliverableJob.id == job_id,
        DeliverableJob.status == DeliverableJobStatus.RUNNING,
        DeliverableJob.artifact_id.is_(None),
    ]
    if task_id is not None:
        conditions.append(DeliverableJob.celery_task_id == task_id)
    return await _transition(
        session,
        conditions,
        status=DeliverableJobStatus.READY,
        phase="ready",
        progress=100,
        artifact_id=artifact_id,
        failure_code=None,
        internal_error=None,
        heartbeat_at=now,
        finished_at=now,
    )


async def fail_deliverable_job(
    session: AsyncSession,
    job_id: int,
    *,
    failure_code: DeliverableFailureCode | str,
    internal_error: str | None = None,
    task_id: str | None = None,
) -> DeliverableJob | None:
    code = DeliverableFailureCode(failure_code).value
    now = _now()
    conditions = [
        DeliverableJob.id == job_id,
        DeliverableJob.status == DeliverableJobStatus.RUNNING,
        DeliverableJob.artifact_id.is_(None),
    ]
    if task_id is not None:
        conditions.append(DeliverableJob.celery_task_id == task_id)
    return await _transition(
        session,
        conditions,
        status=DeliverableJobStatus.FAILED,
        phase="failed",
        failure_code=code,
        internal_error=_bounded_error(internal_error),
        heartbeat_at=now,
        finished_at=now,
    )


async def request_deliverable_job_cancellation(
    session: AsyncSession,
    job_id: int,
) -> DeliverableJob | None:
    """Cancel queued work immediately or request cooperation from a worker."""

    now = _now()
    cancelled = await _transition(
        session,
        [
            DeliverableJob.id == job_id,
            DeliverableJob.status == DeliverableJobStatus.QUEUED,
            DeliverableJob.artifact_id.is_(None),
        ],
        status=DeliverableJobStatus.CANCELLED,
        phase="cancelled",
        failure_code=DeliverableFailureCode.CANCELLED.value,
        cancel_requested_at=now,
        finished_at=now,
    )
    if cancelled is not None:
        return cancelled
    return await _transition(
        session,
        [
            DeliverableJob.id == job_id,
            DeliverableJob.status == DeliverableJobStatus.RUNNING,
            DeliverableJob.artifact_id.is_(None),
        ],
        status=DeliverableJobStatus.CANCELLING,
        phase="cancelling",
        cancel_requested_at=now,
    )


async def cancel_deliverable_job(
    session: AsyncSession,
    job_id: int,
    *,
    task_id: str | None = None,
) -> DeliverableJob | None:
    now = _now()
    conditions = [
        DeliverableJob.id == job_id,
        DeliverableJob.status == DeliverableJobStatus.CANCELLING,
        DeliverableJob.artifact_id.is_(None),
    ]
    if task_id is not None:
        conditions.append(DeliverableJob.celery_task_id == task_id)
    return await _transition(
        session,
        conditions,
        status=DeliverableJobStatus.CANCELLED,
        phase="cancelled",
        failure_code=DeliverableFailureCode.CANCELLED.value,
        internal_error=None,
        heartbeat_at=now,
        finished_at=now,
    )


async def retry_deliverable_job(
    session: AsyncSession,
    job_id: int,
) -> DeliverableJob | None:
    """Reset an explicitly retryable job while preserving its identity."""

    result = await session.execute(
        select(DeliverableJob).where(
            DeliverableJob.id == job_id,
            DeliverableJob.status.in_(
                [DeliverableJobStatus.FAILED, DeliverableJobStatus.CANCELLED]
            ),
            DeliverableJob.artifact_id.is_(None),
        )
    )
    job = result.scalar_one_or_none()
    if job is None:
        return None

    get_deliverable_kind_spec(job.kind)
    next_attempt = job.attempt_count + 1
    return await _transition(
        session,
        [
            DeliverableJob.id == job_id,
            DeliverableJob.status == job.status,
            DeliverableJob.attempt_count == job.attempt_count,
            DeliverableJob.artifact_id.is_(None),
        ],
        status=DeliverableJobStatus.QUEUED,
        phase=None,
        progress=0,
        checkpoint={},
        celery_task_id=task_id_for_attempt(job_id, next_attempt),
        attempt_count=next_attempt,
        failure_code=None,
        internal_error=None,
        cancel_requested_at=None,
        claimed_at=None,
        heartbeat_at=None,
        finished_at=None,
    )


async def list_stale_queued_jobs(
    session: AsyncSession,
    *,
    updated_before: datetime,
    limit: int = 100,
) -> Sequence[DeliverableJob]:
    """Lock a bounded outbox batch for safe reconciliation.

    All stale queued rows are eligible, including rows with a task ID: broker
    publication has no transactional acknowledgement. Deterministic task IDs
    and atomic claims make a duplicate publication harmless.
    """

    if limit <= 0:
        raise ValueError("limit must be positive")
    result = await session.execute(
        select(DeliverableJob)
        .where(
            DeliverableJob.status == DeliverableJobStatus.QUEUED,
            DeliverableJob.updated_at <= updated_before,
        )
        .order_by(DeliverableJob.updated_at, DeliverableJob.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    return result.scalars().all()


async def list_stale_cancelling_jobs(
    session: AsyncSession,
    *,
    heartbeat_before: datetime,
    limit: int = 100,
) -> Sequence[DeliverableJob]:
    """Lock cancelling jobs whose worker has stopped reporting progress."""
    if limit <= 0:
        raise ValueError("limit must be positive")
    result = await session.execute(
        select(DeliverableJob)
        .where(
            DeliverableJob.status == DeliverableJobStatus.CANCELLING,
            DeliverableJob.heartbeat_at <= heartbeat_before,
        )
        .order_by(DeliverableJob.heartbeat_at, DeliverableJob.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    return result.scalars().all()


async def _transition(
    session: AsyncSession,
    conditions: list[Any],
    **values: Any,
) -> DeliverableJob | None:
    values["updated_at"] = _now()
    result = await session.execute(
        update(DeliverableJob)
        .where(*conditions)
        .values(**values)
        .returning(DeliverableJob)
    )
    return result.scalar_one_or_none()


def _bounded_error(error: str | None) -> str | None:
    if error is None:
        return None
    return error[:_MAX_INTERNAL_ERROR_LENGTH]


def _now() -> datetime:
    return datetime.now(UTC)
