"""Authenticated lifecycle controls for queued deliverable jobs."""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import (
    DeliverableJob,
    DeliverableJobStatus,
    Permission,
    get_async_session,
)
from app.deliverables.jobs.dispatch import dispatch_deliverable_job
from app.deliverables.jobs.service import (
    request_deliverable_job_cancellation,
    retry_deliverable_job,
)
from app.users import get_auth_context
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)
router = APIRouter()


class DeliverableJobRead(BaseModel):
    """Public lifecycle projection; worker and billing details stay private."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    title: str
    status: DeliverableJobStatus
    phase: str | None
    progress: int
    failure_code: str | None
    artifact_id: int | None
    workspace_id: int
    thread_id: int | None
    created_at: datetime
    updated_at: datetime


async def _load_job(
    session: AsyncSession,
    workspace_id: int,
    job_id: int,
) -> DeliverableJob:
    job = await session.scalar(
        select(DeliverableJob).where(
            DeliverableJob.id == job_id,
            DeliverableJob.workspace_id == workspace_id,
        )
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Deliverable job not found")
    return job


async def _authorize(
    session: AsyncSession,
    auth: AuthContext,
    workspace_id: int,
    permission: Permission,
) -> None:
    await check_permission(
        session,
        auth,
        workspace_id,
        permission.value,
        "You don't have permission to manage deliverables in this workspace",
    )


@router.get(
    "/workspaces/{workspace_id}/deliverable-jobs/{job_id}",
    response_model=DeliverableJobRead,
)
async def get_deliverable_job(
    workspace_id: int,
    job_id: int,
    response: Response,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> DeliverableJob:
    await _authorize(
        session, auth, workspace_id, Permission.VIDEO_PRESENTATIONS_READ
    )
    response.headers["Cache-Control"] = "private, no-store"
    return await _load_job(session, workspace_id, job_id)


@router.post(
    "/workspaces/{workspace_id}/deliverable-jobs/{job_id}/cancel",
    response_model=DeliverableJobRead,
)
async def cancel_deliverable_job_route(
    workspace_id: int,
    job_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> DeliverableJob:
    await _authorize(
        session, auth, workspace_id, Permission.VIDEO_PRESENTATIONS_UPDATE
    )
    job = await _load_job(session, workspace_id, job_id)
    if job.status in {
        DeliverableJobStatus.CANCELLING,
        DeliverableJobStatus.CANCELLED,
    }:
        return job
    if job.status not in {
        DeliverableJobStatus.QUEUED,
        DeliverableJobStatus.RUNNING,
    }:
        raise HTTPException(
            status_code=409,
            detail="This deliverable can no longer be cancelled",
        )

    cancelled = await request_deliverable_job_cancellation(session, job.id)
    if cancelled is None:
        await session.rollback()
        cancelled = await _load_job(session, workspace_id, job_id)
    await session.commit()
    return cancelled


@router.post(
    "/workspaces/{workspace_id}/deliverable-jobs/{job_id}/retry",
    response_model=DeliverableJobRead,
)
async def retry_deliverable_job_route(
    workspace_id: int,
    job_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> DeliverableJob:
    await _authorize(
        session, auth, workspace_id, Permission.VIDEO_PRESENTATIONS_UPDATE
    )
    job = await _load_job(session, workspace_id, job_id)
    if job.status in {
        DeliverableJobStatus.FAILED,
        DeliverableJobStatus.CANCELLED,
    }:
        queued = await retry_deliverable_job(session, job.id)
        if queued is None:
            await session.rollback()
            queued = await _load_job(session, workspace_id, job_id)
    elif job.status is DeliverableJobStatus.QUEUED and job.attempt_count > 1:
        queued = job
    else:
        raise HTTPException(
            status_code=409,
            detail="This deliverable is not retryable",
        )

    if (
        queued.status is not DeliverableJobStatus.QUEUED
        or not queued.celery_task_id
    ):
        raise HTTPException(
            status_code=409,
            detail="This deliverable is not retryable",
        )

    await session.commit()
    try:
        dispatch_deliverable_job(
            job_id=queued.id,
            task_id=queued.celery_task_id,
        )
    except Exception:
        # The queued row is the durable outbox; reconciliation republishes it.
        logger.exception("Could not publish retried deliverable job %s", queued.id)
    return queued
