from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.dialects import postgresql

from app.db import DeliverableFailureCode, DeliverableJobStatus
from app.deliverables.jobs.policy import VIDEO_SPEC, get_deliverable_kind_spec
from app.deliverables.jobs.service import (
    cancel_deliverable_job,
    claim_deliverable_job,
    complete_deliverable_job,
    create_deliverable_job,
    fail_deliverable_job,
    heartbeat_deliverable_job,
    list_stale_queued_jobs,
    request_deliverable_job_cancellation,
    retry_deliverable_job,
    task_id_for_attempt,
)

pytestmark = pytest.mark.unit


class _Result:
    def __init__(self, value: Any) -> None:
        self.value = value

    def scalar_one_or_none(self) -> Any:
        return self.value

    def scalar_one(self) -> Any:
        assert self.value is not None
        return self.value

    def scalars(self) -> _Result:
        return self

    def all(self) -> Any:
        return self.value


class _Session:
    def __init__(self, *results: Any) -> None:
        self.results = list(results)
        self.statements: list[Any] = []

    async def execute(self, statement: Any) -> _Result:
        self.statements.append(statement)
        return _Result(self.results.pop(0))


def _params(statement: Any) -> dict[str, Any]:
    return statement.compile(dialect=postgresql.dialect()).params


def test_video_policy_is_bounded() -> None:
    spec = get_deliverable_kind_spec("video")

    assert spec is VIDEO_SPEC
    assert spec.max_duration_seconds == 180
    assert spec.max_scenes == 12
    assert spec.repair_cycles == 2
    assert 0 < spec.soft_time_limit_seconds < spec.hard_time_limit_seconds


async def test_create_is_idempotent_on_workspace_kind_and_tool_call() -> None:
    existing = SimpleNamespace(id=7, attempt_count=1)
    session = _Session(None, existing)

    job, created = await create_deliverable_job(
        session,
        kind="video",
        title="Quarterly update",
        workspace_id=3,
        tool_call_id="call-1",
        request={"brief": "Explain revenue"},
    )

    insert_sql = str(session.statements[0].compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT ON CONSTRAINT" in insert_sql
    assert job is existing
    assert created is False
    assert len(session.statements) == 2


async def test_new_job_gets_deterministic_first_attempt_task_id() -> None:
    created_job = SimpleNamespace(id=9, attempt_count=1)
    session = _Session(9, None, created_job)

    job, created = await create_deliverable_job(
        session,
        kind="video",
        title="Launch",
        workspace_id=3,
        tool_call_id="call-2",
        request={},
    )

    assert created is True
    assert job is created_job
    assert task_id_for_attempt(9, 1) in _params(session.statements[1]).values()


async def test_atomic_claim_only_returns_one_duplicate_delivery() -> None:
    claimed = SimpleNamespace(id=5, status=DeliverableJobStatus.RUNNING)
    session = _Session(claimed, None)

    first = await claim_deliverable_job(
        session,
        5,
        task_id="deliverable-job:5:attempt:1",
        attempt_count=1,
    )
    duplicate = await claim_deliverable_job(
        session,
        5,
        task_id="deliverable-job:5:attempt:1",
        attempt_count=1,
    )

    assert first is claimed
    assert duplicate is None
    for statement in session.statements:
        params = _params(statement)
        assert DeliverableJobStatus.QUEUED in params.values()
        assert DeliverableJobStatus.RUNNING in params.values()


async def test_failure_code_is_typed_and_internal_error_is_bounded() -> None:
    failed = SimpleNamespace(id=5, status=DeliverableJobStatus.FAILED)
    session = _Session(failed)

    result = await fail_deliverable_job(
        session,
        5,
        failure_code=DeliverableFailureCode.RENDER_FAILED,
        internal_error="x" * 3000,
    )

    assert result is failed
    params = _params(session.statements[0])
    assert DeliverableFailureCode.RENDER_FAILED.value in params.values()
    assert "x" * 2000 in params.values()
    assert "x" * 2001 not in params.values()


async def test_running_attempt_transitions_are_bound_to_celery_task_id() -> None:
    task_id = "deliverable-job:5:attempt:2"
    session = _Session(
        SimpleNamespace(id=5),
        SimpleNamespace(id=5),
        SimpleNamespace(id=5),
        SimpleNamespace(id=5),
    )

    await heartbeat_deliverable_job(
        session,
        5,
        phase="rendering",
        progress=50,
        task_id=task_id,
    )
    await complete_deliverable_job(session, 5, artifact_id=8, task_id=task_id)
    await fail_deliverable_job(
        session,
        5,
        failure_code=DeliverableFailureCode.RENDER_FAILED,
        task_id=task_id,
    )
    await cancel_deliverable_job(session, 5, task_id=task_id)

    assert all(task_id in _params(statement).values() for statement in session.statements)


async def test_running_cancellation_uses_cooperative_cancelling_state() -> None:
    cancelling = SimpleNamespace(id=5, status=DeliverableJobStatus.CANCELLING)
    session = _Session(None, cancelling)

    result = await request_deliverable_job_cancellation(session, 5)

    assert result is cancelling
    queued_params = _params(session.statements[0])
    running_params = _params(session.statements[1])
    assert DeliverableJobStatus.QUEUED in queued_params.values()
    assert DeliverableJobStatus.CANCELLED in queued_params.values()
    assert DeliverableJobStatus.RUNNING in running_params.values()
    assert DeliverableJobStatus.CANCELLING in running_params.values()


async def test_queued_cancellation_finishes_without_running_transition() -> None:
    cancelled = SimpleNamespace(id=5, status=DeliverableJobStatus.CANCELLED)
    session = _Session(cancelled)

    result = await request_deliverable_job_cancellation(session, 5)

    assert result is cancelled
    assert len(session.statements) == 1


async def test_progress_and_ready_artifact_are_bounded() -> None:
    session = _Session()

    with pytest.raises(ValueError, match="between 0 and 99"):
        await heartbeat_deliverable_job(
            session,
            5,
            phase="rendering",
            progress=100,
        )
    with pytest.raises(ValueError, match="phase must be between"):
        await heartbeat_deliverable_job(
            session,
            5,
            phase="x" * 65,
            progress=50,
        )
    with pytest.raises(ValueError, match="require an artifact"):
        await complete_deliverable_job(session, 5, artifact_id=0)

    assert session.statements == []


async def test_retry_preserves_identity_and_advances_attempt() -> None:
    failed = SimpleNamespace(
        id=12,
        kind="video",
        status=DeliverableJobStatus.FAILED,
        attempt_count=2,
    )
    queued = SimpleNamespace(
        id=12,
        status=DeliverableJobStatus.QUEUED,
        attempt_count=3,
    )
    session = _Session(failed, queued)

    result = await retry_deliverable_job(session, 12)

    assert result is queued
    params = _params(session.statements[1])
    assert 3 in params.values()
    assert task_id_for_attempt(12, 3) in params.values()
    assert DeliverableJobStatus.QUEUED in params.values()


async def test_outbox_locks_all_stale_queued_rows_for_republication() -> None:
    jobs = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
    session = _Session(jobs)

    result = await list_stale_queued_jobs(
        session,
        updated_before=datetime(2026, 1, 1, tzinfo=UTC),
        limit=2,
    )

    sql = str(session.statements[0].compile(dialect=postgresql.dialect()))
    assert result == jobs
    assert "FOR UPDATE SKIP LOCKED" in sql
    assert "celery_task_id IS NULL" not in sql
