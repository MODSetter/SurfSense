from __future__ import annotations

import asyncio
import inspect
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

from app.celery_app import celery_app
from app.db import DeliverableFailureCode
from app.deliverables.jobs.dispatch import DELIVERABLE_JOB_TASK
from app.deliverables.jobs.policy import VIDEO_SPEC
from app.tasks.celery_tasks import deliverable_job_tasks as tasks

pytestmark = pytest.mark.unit


class _Session:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def _session_maker(session: _Session):
    @asynccontextmanager
    async def context():
        yield session

    return context


def _job(**overrides: Any) -> SimpleNamespace:
    values = {
        "id": 17,
        "kind": "video",
        "title": "Launch update",
        "workspace_id": 3,
        "thread_id": 44,
        "created_by_id": None,
        "celery_task_id": "deliverable-job:17:attempt:1",
        "attempt_count": 1,
        "request": {
            "version": 1,
            "brief": "Explain the launch",
            "source_references": ["/documents/brief.md"],
            "revision_artifact_id": None,
            "root_thread_id": 44,
        },
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_task_registration_is_late_acked_bounded_and_uses_default_queue() -> None:
    task = celery_app.tasks[DELIVERABLE_JOB_TASK]

    assert task.acks_late is True
    assert task.reject_on_worker_lost is True
    assert task.soft_time_limit == VIDEO_SPEC.soft_time_limit_seconds
    assert task.time_limit == VIDEO_SPEC.hard_time_limit_seconds
    assert celery_app.conf.worker_prefetch_multiplier == 1
    assert DELIVERABLE_JOB_TASK not in celery_app.conf.task_routes


def test_worker_has_no_queued_subagent_or_checkpointer_dependencies() -> None:
    assert not hasattr(tasks, "run_deliverable_subagent")
    assert not hasattr(tasks, "get_checkpointer")
    assert not hasattr(tasks, "build_trusted_video_prompt")
    assert "job.id" not in inspect.getsource(tasks._execute_queued_deliverable)


def test_failure_classification_is_terminal_or_transient_and_sanitized() -> None:
    class RateLimitError(Exception):
        pass

    assert tasks.classify_deliverable_failure(RuntimeError("verification failed")) == (
        DeliverableFailureCode.VERIFICATION_FAILED,
        False,
    )
    assert tasks.classify_deliverable_failure(
        RateLimitError("provider rate limit")
    ) == (DeliverableFailureCode.GENERATION_FAILED, True)
    assert tasks.classify_deliverable_failure(
        TimeoutError("sandbox operation timed out")
    ) == (DeliverableFailureCode.GENERATION_FAILED, False)
    assert tasks.classify_deliverable_failure(
        RuntimeError("duration limit exceeded")
    ) == (DeliverableFailureCode.DURATION_LIMIT, False)

    diagnostic = tasks.sanitize_internal_error(
        RuntimeError("api_key=super-secret https://user:pass@broker.example/internal")
    )
    assert "super-secret" not in diagnostic
    assert "user:pass" not in diagnostic
    assert "[redacted]" in diagnostic


async def test_duplicate_delivery_is_ignored_before_executor_run(monkeypatch) -> None:
    session = _Session()
    ran = False

    async def claim(*_args, **_kwargs):
        return None

    async def run(*_args, **_kwargs):
        nonlocal ran
        ran = True

    monkeypatch.setattr(
        tasks, "get_celery_session_maker", lambda: _session_maker(session)
    )
    monkeypatch.setattr(tasks, "claim_deliverable_job", claim)
    monkeypatch.setattr(tasks, "execute_video_deliverable", run)

    result = await tasks._execute_queued_deliverable(
        17,
        task_id="deliverable-job:17:attempt:1",
        retry_provider_failure=True,
    )

    assert result == {"status": "ignored", "job_id": 17}
    assert ran is False
    assert session.rollbacks == 1


async def test_worker_calls_executor_bills_llm_only_and_terminates_sandbox(
    monkeypatch,
) -> None:
    session = _Session()
    job = _job()
    billable_kwargs = {}
    executor_args = ()
    terminated = []

    async def claim(*_args, **_kwargs):
        return job

    async def resolve_model(*_args, **_kwargs):
        class LLM:
            async def ainvoke(self, messages):
                return ("response", messages)

        return LLM(), SimpleNamespace(quota_reserve_tokens=2048)

    async def resolve_billing(*_args, **_kwargs):
        return SimpleNamespace(), "free", "model"

    @asynccontextmanager
    async def billable(**kwargs):
        billable_kwargs.update(kwargs)
        yield object()

    async def execute(session_arg, job_arg, llm):
        nonlocal executor_args
        executor_args = (session_arg, job_arg)
        assert await llm.ainvoke(["author"]) == ("response", ["author"])
        return SimpleNamespace(artifact_id=91)

    async def complete(*_args, **_kwargs):
        return SimpleNamespace(id=17)

    class Registry:
        async def terminate(self, owner):
            terminated.append(owner)

    async def registry():
        return Registry()

    monkeypatch.setattr(
        tasks, "get_celery_session_maker", lambda: _session_maker(session)
    )
    monkeypatch.setattr(tasks, "claim_deliverable_job", claim)
    monkeypatch.setattr(tasks, "_resolve_worker_model", resolve_model)
    monkeypatch.setattr(tasks, "_resolve_agent_billing_for_workspace", resolve_billing)
    monkeypatch.setattr(tasks, "billable_call", billable)
    monkeypatch.setattr(tasks, "execute_video_deliverable", execute)
    monkeypatch.setattr(tasks, "complete_deliverable_job", complete)
    monkeypatch.setattr(tasks, "get_registry", registry)

    result = await tasks._execute_queued_deliverable(
        17,
        task_id=job.celery_task_id,
        retry_provider_failure=True,
    )

    assert result == {"status": "ready", "job_id": 17, "artifact_id": 91}
    assert executor_args == (session, job)
    assert terminated == ["deliverable-job-17-attempt-1"]
    assert billable_kwargs["quota_reserve_tokens"] == 2048
    assert "quota_reserve_micros_override" not in billable_kwargs
    assert billable_kwargs["usage_type"] == "queued_deliverable_generation"
    assert billable_kwargs["call_details"] == {
        "deliverable_job_id": 17,
        "kind": "video",
    }


async def test_cooperative_cancellation_finishes_state_and_cleans_sandbox(
    monkeypatch,
) -> None:
    session = _Session()
    job = _job()
    cancelled = []
    terminated = []

    async def claim(*_args, **_kwargs):
        return job

    async def resolve_model(*_args, **_kwargs):
        return object(), SimpleNamespace(quota_reserve_tokens=None)

    async def resolve_billing(*_args, **_kwargs):
        return SimpleNamespace(), "free", "model"

    async def execute(*_args, **_kwargs):
        raise tasks.DeliverableJobCancellationError

    async def cancel(_session, job_id, **_kwargs):
        cancelled.append(job_id)
        return SimpleNamespace(id=job_id)

    class Registry:
        async def terminate(self, owner):
            terminated.append(owner)

    async def registry():
        return Registry()

    monkeypatch.setattr(
        tasks, "get_celery_session_maker", lambda: _session_maker(session)
    )
    monkeypatch.setattr(tasks, "claim_deliverable_job", claim)
    monkeypatch.setattr(tasks, "_resolve_worker_model", resolve_model)
    monkeypatch.setattr(tasks, "_resolve_agent_billing_for_workspace", resolve_billing)
    monkeypatch.setattr(tasks, "execute_video_deliverable", execute)
    monkeypatch.setattr(tasks, "cancel_deliverable_job", cancel)
    monkeypatch.setattr(tasks, "get_registry", registry)

    result = await tasks._execute_queued_deliverable(
        17,
        task_id=job.celery_task_id,
        retry_provider_failure=True,
    )

    assert result == {"status": "cancelled", "job_id": 17}
    assert cancelled == [17]
    assert terminated == ["deliverable-job-17-attempt-1"]
    assert session.rollbacks == 1
    assert session.commits == 2


async def test_cancellation_watcher_stops_work_and_attempt_sandbox(monkeypatch) -> None:
    work_cancelled = asyncio.Event()
    terminated = []

    async def work():
        try:
            await asyncio.Event().wait()
        finally:
            work_cancelled.set()

    async def watch(*_args, **_kwargs):
        await asyncio.sleep(0)
        return "cancelled"

    class Registry:
        async def terminate(self, owner):
            terminated.append(owner)

    async def registry():
        return Registry()

    monkeypatch.setattr(tasks, "_wait_for_cancellation", watch)
    monkeypatch.setattr(tasks, "get_registry", registry)

    with pytest.raises(tasks.DeliverableJobCancellationError):
        await tasks._run_with_cancellation(
            work(),
            job_id=17,
            task_id="deliverable-job:17:attempt:2",
            sandbox_owner="deliverable-job-17-attempt-2",
        )

    assert work_cancelled.is_set()
    assert terminated == ["deliverable-job-17-attempt-2"]


async def test_reconciliation_republishes_each_job_to_default_queue(
    monkeypatch,
) -> None:
    session = _Session()
    jobs = [_job(id=17), _job(id=18, celery_task_id="deliverable-job:18:attempt:1")]
    dispatched = []

    async def list_jobs(*_args, **_kwargs):
        return jobs

    async def list_cancelling(*_args, **_kwargs):
        return []

    def dispatch(**kwargs):
        dispatched.append(kwargs)

    monkeypatch.setattr(
        tasks, "get_celery_session_maker", lambda: _session_maker(session)
    )
    monkeypatch.setattr(tasks, "list_stale_queued_jobs", list_jobs)
    monkeypatch.setattr(tasks, "list_stale_cancelling_jobs", list_cancelling)
    monkeypatch.setattr(tasks, "dispatch_deliverable_job", dispatch)

    count = await tasks._reconcile_stale_queued()

    assert count == 2
    assert [item["task_id"] for item in dispatched] == [
        "deliverable-job:17:attempt:1",
        "deliverable-job:18:attempt:1",
    ]
    assert all(set(item) == {"job_id", "task_id"} for item in dispatched)
    assert session.commits == 1


async def test_reconciliation_finishes_stale_cancellation_and_attempt_sandbox(
    monkeypatch,
) -> None:
    session = _Session()
    job = _job(attempt_count=2, celery_task_id="deliverable-job:17:attempt:2")
    cancelled = []
    terminated = []

    async def list_queued(*_args, **_kwargs):
        return []

    async def list_cancelling(*_args, **_kwargs):
        return [job]

    async def cancel(_session, job_id, **kwargs):
        cancelled.append((job_id, kwargs["task_id"]))
        return job

    class Registry:
        async def terminate(self, owner):
            terminated.append(owner)

    async def registry():
        return Registry()

    monkeypatch.setattr(
        tasks, "get_celery_session_maker", lambda: _session_maker(session)
    )
    monkeypatch.setattr(tasks, "list_stale_queued_jobs", list_queued)
    monkeypatch.setattr(tasks, "list_stale_cancelling_jobs", list_cancelling)
    monkeypatch.setattr(tasks, "cancel_deliverable_job", cancel)
    monkeypatch.setattr(tasks, "get_registry", registry)

    assert await tasks._reconcile_stale_queued() == 0
    assert cancelled == [(17, "deliverable-job:17:attempt:2")]
    assert terminated == ["deliverable-job-17-attempt-2"]


async def test_terminal_failure_is_persisted_without_raw_public_error(
    monkeypatch,
) -> None:
    session = _Session()
    calls = []

    async def fail(*_args, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(id=17)

    async def cancel(*_args, **_kwargs):
        raise AssertionError("terminal running failure should not cancel")

    monkeypatch.setattr(tasks, "fail_deliverable_job", fail)
    monkeypatch.setattr(tasks, "cancel_deliverable_job", cancel)

    await tasks._finish_failure(
        session,
        17,
        failure_code=DeliverableFailureCode.RENDER_FAILED,
        diagnostic="RuntimeError: internal only",
        task_id="deliverable-job:17:attempt:1",
    )

    assert calls == [
        {
            "failure_code": DeliverableFailureCode.RENDER_FAILED,
            "internal_error": "RuntimeError: internal only",
            "task_id": "deliverable-job:17:attempt:1",
        }
    ]
    assert session.commits == 1


@pytest.mark.parametrize(
    "compose_name",
    ["docker-compose.yml", "docker-compose.dev.yml"],
)
def test_compose_uses_shared_celery_worker_for_video(compose_name: str) -> None:
    repo = Path(__file__).resolve().parents[4]
    compose = yaml.safe_load((repo / "docker" / compose_name).read_text())

    assert "celery_worker" in compose["services"]
    environment = compose["services"]["celery_worker"]["environment"]
    if isinstance(environment, list):
        environment = {
            item.split("=", 1)[0]: item.split("=", 1)[1] for item in environment
        }
    assert {
        "SANDBOX_ENABLED",
        "SANDBOX_PROVIDER",
        "OPENSANDBOX_DOMAIN",
        "OPENSANDBOX_API_KEY",
        "SANDBOX_IMAGE",
    } <= environment.keys()

    entrypoint = (
        repo / "surfsense_backend" / "scripts" / "docker" / "entrypoint.sh"
    ).read_text()
    assert "${DEFAULT_Q},${DEFAULT_Q}.connectors,${DEFAULT_Q}.gateway" in entrypoint
