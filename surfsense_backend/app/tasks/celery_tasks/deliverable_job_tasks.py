"""Celery execution and outbox reconciliation for queued deliverables."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

from billiard.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select

from app.celery_app import celery_app
from app.db import (
    DeliverableFailureCode,
    DeliverableJob,
    DeliverableJobStatus,
    Workspace,
)
from app.deliverables.jobs.dispatch import (
    DELIVERABLE_JOB_TASK,
    dispatch_deliverable_job,
)
from app.deliverables.jobs.policy import (
    VIDEO_KIND,
    VIDEO_SPEC,
    get_deliverable_kind_spec,
)
from app.deliverables.jobs.service import (
    cancel_deliverable_job,
    claim_deliverable_job,
    complete_deliverable_job,
    fail_deliverable_job,
    list_stale_cancelling_jobs,
    list_stale_queued_jobs,
    requeue_claimed_deliverable_job,
)
from app.deliverables.video.executor import (
    DeliverableJobCancellationError,
    execute_video_deliverable,
    video_sandbox_owner,
)
from app.sandbox import get_registry
from app.services.billable_calls import (
    BillingSettlementError,
    QuotaInsufficientError,
    _resolve_agent_billing_for_workspace,
    billable_call,
)
from app.services.llm_error_adapter import adapt_llm_exception
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task
from app.tasks.chat.streaming.flows.new_chat.auto_pin import resolve_initial_auto_pin
from app.tasks.chat.streaming.flows.shared.llm_bundle import load_llm_bundle

logger = logging.getLogger(__name__)

RECONCILE_TASK = "deliverables.reconcile_queued"
_OUTBOX_STALE_AFTER = timedelta(minutes=2)
_CANCELLING_STALE_AFTER = timedelta(minutes=5)
_CANCEL_POLL_SECONDS = 0.5
_OUTBOX_BATCH_SIZE = 100
_MAX_PROVIDER_RETRIES = 3
_MAX_DIAGNOSTIC_CHARS = 1200
_SECRET_PATTERN = re.compile(
    r"(?i)(api[_-]?key|authorization|password|secret|token)\s*[:=]\s*\S+"
)
_URL_CREDENTIALS_PATTERN = re.compile(r"(?i)([a-z][a-z0-9+.-]*://)[^/@\s]+@")
_TRANSIENT_PROVIDER_EXCEPTION_NAMES = {
    "APIConnectionError",
    "APITimeoutError",
    "BadGatewayError",
    "ConnectError",
    "ConnectTimeout",
    "GatewayTimeoutError",
    "InternalServerError",
    "RateLimitError",
    "ReadTimeout",
    "ServiceUnavailableError",
    "TooManyRequests",
    "TooManyRequestsError",
}


class _SupersededAttemptError(Exception):
    """Stop an old worker after a retry has advanced the job attempt."""


@asynccontextmanager
async def _celery_billable_session():
    async with get_celery_session_maker()() as session:
        yield session


class _BillableQueuedLLM:
    """Bill only the executor's targeted authoring and repair LLM calls."""

    def __init__(
        self,
        llm,
        *,
        user_id,
        workspace_id: int,
        billing_tier: str,
        base_model: str,
        quota_reserve_tokens: int | None,
        thread_id: int,
        job_id: int,
    ) -> None:
        self._llm = llm
        self._billing = {
            "user_id": user_id,
            "workspace_id": workspace_id,
            "billing_tier": billing_tier,
            "base_model": base_model,
            "quota_reserve_tokens": quota_reserve_tokens,
            "usage_type": "queued_deliverable_generation",
            "thread_id": thread_id,
            "call_details": {"deliverable_job_id": job_id, "kind": VIDEO_KIND},
            "billable_session_factory": _celery_billable_session,
        }

    async def ainvoke(self, *args, **kwargs):
        async with billable_call(**self._billing):
            return await self._llm.ainvoke(*args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self._llm, name)


def classify_deliverable_failure(
    exc: BaseException,
) -> tuple[DeliverableFailureCode, bool]:
    """Map internal exceptions to stable public state and retry eligibility."""
    if isinstance(exc, QuotaInsufficientError):
        return DeliverableFailureCode.QUOTA_EXCEEDED, False
    if isinstance(exc, BillingSettlementError):
        return DeliverableFailureCode.GENERATION_FAILED, False

    message = str(exc).lower()
    if "out of credits" in message or "quota" in message:
        return DeliverableFailureCode.QUOTA_EXCEEDED, False
    if "duration" in message and ("limit" in message or "180" in message):
        return DeliverableFailureCode.DURATION_LIMIT, False
    if "verif" in message or "no verified artifact" in message:
        return DeliverableFailureCode.VERIFICATION_FAILED, False
    if isinstance(exc, SoftTimeLimitExceeded) or any(
        marker in message
        for marker in ("remotion", "render", "ffmpeg", "chromium", "chrome")
    ):
        return DeliverableFailureCode.RENDER_FAILED, False

    adaptation = adapt_llm_exception(exc)
    class_names = {cls.__name__ for cls in type(exc).__mro__}
    provider_transient = adaptation.retryable and bool(
        class_names & _TRANSIENT_PROVIDER_EXCEPTION_NAMES
    )
    return DeliverableFailureCode.GENERATION_FAILED, provider_transient


def sanitize_internal_error(exc: BaseException) -> str:
    """Bound diagnostics and remove common credential forms before persistence."""
    text = " ".join(str(exc).split())
    text = _SECRET_PATTERN.sub(r"\1=[redacted]", text)
    text = _URL_CREDENTIALS_PATTERN.sub(r"\1[redacted]@", text)
    return f"{type(exc).__name__}: {text}"[:_MAX_DIAGNOSTIC_CHARS]


async def _resolve_worker_model(session, job: DeliverableJob):
    workspace = (
        await session.execute(select(Workspace).where(Workspace.id == job.workspace_id))
    ).scalar_one_or_none()
    if workspace is None or workspace.chat_model_id is None:
        raise ValueError("workspace chat model is unavailable")
    if job.thread_id is None:
        raise ValueError("queued deliverable requires a root thread")

    config_id = workspace.chat_model_id
    requesting_user_id = str(job.created_by_id or workspace.user_id)
    if config_id == 0:
        pin = await resolve_initial_auto_pin(
            session,
            chat_id=job.thread_id,
            workspace_id=job.workspace_id,
            user_id=requesting_user_id,
            selected_llm_config_id=0,
            requires_image_input=False,
            requested_llm_config_id=0,
        )
        if pin.error is not None or pin.llm_config_id is None:
            raise ValueError("workspace chat model could not be resolved")
        config_id = pin.llm_config_id

    llm, agent_config, error = await load_llm_bundle(
        session,
        config_id=config_id,
        workspace_id=job.workspace_id,
    )
    if llm is None or agent_config is None or error is not None:
        raise ValueError("workspace chat model could not be loaded")
    return llm, agent_config


async def _finish_failure(
    session,
    job_id: int,
    *,
    failure_code: DeliverableFailureCode,
    diagnostic: str,
    task_id: str | None,
) -> None:
    failed = await fail_deliverable_job(
        session,
        job_id,
        failure_code=failure_code,
        internal_error=diagnostic,
        task_id=task_id,
    )
    if failed is None:
        await cancel_deliverable_job(session, job_id, task_id=task_id)
    await session.commit()


async def _wait_for_cancellation(job_id: int, task_id: str | None) -> str:
    """Watch durable job state without sharing the executor's session."""
    await asyncio.sleep(_CANCEL_POLL_SECONDS)
    session_maker = get_celery_session_maker()
    while True:
        try:
            async with session_maker() as session:
                row = (
                    await session.execute(
                        select(
                            DeliverableJob.status,
                            DeliverableJob.celery_task_id,
                        ).where(DeliverableJob.id == job_id)
                    )
                ).one_or_none()
            if row is None or (task_id is not None and row.celery_task_id != task_id):
                return "superseded"
            if row.status in {
                DeliverableJobStatus.CANCELLING,
                DeliverableJobStatus.CANCELLED,
            }:
                return "cancelled"
            if row.status != DeliverableJobStatus.RUNNING:
                return "superseded"
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning(
                "Could not poll cancellation state for deliverable job %s",
                job_id,
                exc_info=True,
            )
        await asyncio.sleep(_CANCEL_POLL_SECONDS)


async def _run_with_cancellation(
    work,
    *,
    job_id: int,
    task_id: str | None,
    sandbox_owner: str,
):
    work_task = asyncio.create_task(work)
    watcher = asyncio.create_task(_wait_for_cancellation(job_id, task_id))
    done, _ = await asyncio.wait(
        {work_task, watcher},
        return_when=asyncio.FIRST_COMPLETED,
    )
    if work_task in done:
        watcher.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await watcher
        return await work_task

    outcome = await watcher
    work_task.cancel()
    try:
        await (await get_registry()).terminate(sandbox_owner)
    except Exception:
        logger.warning(
            "Could not immediately terminate sandbox %s during cancellation",
            sandbox_owner,
            exc_info=True,
        )
    await asyncio.gather(work_task, return_exceptions=True)
    if outcome == "cancelled":
        raise DeliverableJobCancellationError
    raise _SupersededAttemptError


async def _execute_claimed_deliverable(
    session,
    job: DeliverableJob,
    *,
    job_id: int,
    task_id: str | None,
) -> dict[str, Any]:
    llm, agent_config = await _resolve_worker_model(session, job)
    owner_id, billing_tier, base_model = await _resolve_agent_billing_for_workspace(
        session,
        job.workspace_id,
        thread_id=job.thread_id,
    )
    billed_llm = _BillableQueuedLLM(
        llm,
        user_id=owner_id,
        workspace_id=job.workspace_id,
        billing_tier=billing_tier,
        base_model=base_model,
        quota_reserve_tokens=agent_config.quota_reserve_tokens,
        thread_id=job.thread_id,
        job_id=job_id,
    )
    result = await execute_video_deliverable(session, job, billed_llm)
    ready = await complete_deliverable_job(
        session,
        job_id,
        artifact_id=result.artifact_id,
        task_id=task_id,
    )
    if ready is None:
        raise DeliverableJobCancellationError
    await session.commit()
    return {
        "status": "ready",
        "job_id": job_id,
        "artifact_id": result.artifact_id,
    }


async def _execute_queued_deliverable(
    job_id: int,
    *,
    task_id: str | None,
    retry_provider_failure: bool,
) -> dict[str, Any]:
    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        job = await claim_deliverable_job(session, job_id, task_id=task_id)
        if job is None:
            await session.rollback()
            return {"status": "ignored", "job_id": job_id}
        await session.commit()
        attempt_count = job.attempt_count
        sandbox_owner = video_sandbox_owner(job_id, attempt_count)

        try:
            return await _run_with_cancellation(
                _execute_claimed_deliverable(
                    session,
                    job,
                    job_id=job_id,
                    task_id=task_id,
                ),
                job_id=job_id,
                task_id=task_id,
                sandbox_owner=sandbox_owner,
            )
        except DeliverableJobCancellationError:
            await session.rollback()
            await cancel_deliverable_job(session, job_id, task_id=task_id)
            await session.commit()
            return {"status": "cancelled", "job_id": job_id}
        except _SupersededAttemptError:
            await session.rollback()
            return {"status": "ignored", "job_id": job_id}
        except Exception as exc:
            await session.rollback()
            failure_code, transient = classify_deliverable_failure(exc)
            diagnostic = sanitize_internal_error(exc)
            logger.warning(
                "Queued deliverable job %s failed (%s, transient=%s)",
                job_id,
                failure_code.value,
                transient,
                exc_info=True,
            )
            if transient and retry_provider_failure:
                requeued = await requeue_claimed_deliverable_job(
                    session,
                    job_id,
                    task_id=task_id,
                    internal_error=diagnostic,
                )
                await session.commit()
                if requeued is not None:
                    return {"status": "retry", "job_id": job_id}
            await _finish_failure(
                session,
                job_id,
                failure_code=failure_code,
                diagnostic=diagnostic,
                task_id=task_id,
            )
            return {
                "status": "failed",
                "job_id": job_id,
                "failure_code": failure_code.value,
            }
        finally:
            try:
                await (await get_registry()).terminate(sandbox_owner)
            except Exception:
                logger.warning(
                    "Could not terminate sandbox for queued deliverable job %s",
                    job_id,
                    exc_info=True,
                )


@celery_app.task(
    bind=True,
    name=DELIVERABLE_JOB_TASK,
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=_MAX_PROVIDER_RETRIES,
    soft_time_limit=VIDEO_SPEC.soft_time_limit_seconds,
    time_limit=VIDEO_SPEC.hard_time_limit_seconds,
)
def execute_queued_deliverable(self, job_id: int) -> dict[str, Any]:
    retries = int(getattr(self.request, "retries", 0) or 0)
    outcome = run_async_celery_task(
        lambda: _execute_queued_deliverable(
            job_id,
            task_id=getattr(self.request, "id", None),
            retry_provider_failure=retries < _MAX_PROVIDER_RETRIES,
        )
    )
    if outcome["status"] == "retry":
        raise self.retry(
            countdown=min(60, 2 ** (retries + 1)),
            exc=RuntimeError("transient deliverable provider failure"),
        )
    return outcome


async def _reconcile_stale_queued() -> int:
    dispatched = 0
    stale_sandbox_owners: list[str] = []
    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        jobs = await list_stale_queued_jobs(
            session,
            updated_before=datetime.now(UTC) - _OUTBOX_STALE_AFTER,
            limit=_OUTBOX_BATCH_SIZE,
        )
        for job in jobs:
            try:
                get_deliverable_kind_spec(job.kind)
                if not job.celery_task_id:
                    raise ValueError("queued deliverable has no task identity")
                dispatch_deliverable_job(
                    job_id=job.id,
                    task_id=job.celery_task_id,
                )
                dispatched += 1
            except Exception:
                logger.warning(
                    "Could not reconcile queued deliverable job %s",
                    job.id,
                    exc_info=True,
                )
        cancelling = await list_stale_cancelling_jobs(
            session,
            heartbeat_before=datetime.now(UTC) - _CANCELLING_STALE_AFTER,
            limit=_OUTBOX_BATCH_SIZE,
        )
        for job in cancelling:
            cancelled = await cancel_deliverable_job(
                session,
                job.id,
                task_id=job.celery_task_id,
            )
            if cancelled is not None:
                stale_sandbox_owners.append(
                    video_sandbox_owner(job.id, job.attempt_count)
                )
        await session.commit()
    for owner in stale_sandbox_owners:
        try:
            await (await get_registry()).terminate(owner)
        except Exception:
            logger.warning(
                "Could not terminate stale cancelling sandbox %s",
                owner,
                exc_info=True,
            )
    return dispatched


@celery_app.task(name=RECONCILE_TASK)
def reconcile_stale_queued_deliverables() -> int:
    return run_async_celery_task(_reconcile_stale_queued)
