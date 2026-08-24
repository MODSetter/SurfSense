from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from app.db import DeliverableJobStatus, Permission
from app.routes import deliverable_jobs_routes as routes


def _job(**overrides):
    values = {
        "id": 17,
        "kind": "video",
        "title": "Launch update",
        "status": DeliverableJobStatus.FAILED,
        "phase": "failed",
        "progress": 65,
        "failure_code": "render_failed",
        "artifact_id": None,
        "workspace_id": 3,
        "thread_id": 44,
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 1, 2, tzinfo=UTC),
        "attempt_count": 1,
        "celery_task_id": "deliverable-job:17:attempt:1",
        "request": {"secret": "private"},
        "internal_error": "private diagnostic",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


async def test_cancel_is_workspace_rbac_scoped_and_calls_state_service(
    monkeypatch,
) -> None:
    running = _job(status=DeliverableJobStatus.RUNNING)
    cancelling = _job(
        status=DeliverableJobStatus.CANCELLING,
        phase="cancelling",
    )
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=running),
        commit=AsyncMock(),
    )
    permission = AsyncMock()
    cancel = AsyncMock(return_value=cancelling)
    monkeypatch.setattr(routes, "check_permission", permission)
    monkeypatch.setattr(routes, "request_deliverable_job_cancellation", cancel)

    result = await routes.cancel_deliverable_job_route(
        3, 17, session, SimpleNamespace()
    )

    assert result is cancelling
    permission.assert_awaited_once()
    assert permission.await_args.args[3] == Permission.VIDEO_PRESENTATIONS_UPDATE.value
    cancel.assert_awaited_once_with(session, 17)
    session.commit.assert_awaited_once()


async def test_cancel_is_idempotent_after_cancellation(monkeypatch) -> None:
    cancelled = _job(status=DeliverableJobStatus.CANCELLED)
    monkeypatch.setattr(routes, "_authorize", AsyncMock())
    monkeypatch.setattr(routes, "_load_job", AsyncMock(return_value=cancelled))
    cancel = AsyncMock()
    monkeypatch.setattr(routes, "request_deliverable_job_cancellation", cancel)

    result = await routes.cancel_deliverable_job_route(
        3, 17, SimpleNamespace(), SimpleNamespace()
    )

    assert result is cancelled
    cancel.assert_not_awaited()


async def test_retry_reuses_job_identity_and_dispatches_on_default_queue(
    monkeypatch,
) -> None:
    failed = _job()
    queued = _job(
        status=DeliverableJobStatus.QUEUED,
        phase=None,
        progress=0,
        failure_code=None,
        attempt_count=2,
        celery_task_id="deliverable-job:17:attempt:2",
    )
    session = SimpleNamespace(commit=AsyncMock())
    monkeypatch.setattr(routes, "_authorize", AsyncMock())
    monkeypatch.setattr(routes, "_load_job", AsyncMock(return_value=failed))
    retry = AsyncMock(return_value=queued)
    dispatch = Mock()
    monkeypatch.setattr(routes, "retry_deliverable_job", retry)
    monkeypatch.setattr(routes, "dispatch_deliverable_job", dispatch)

    result = await routes.retry_deliverable_job_route(
        3, 17, session, SimpleNamespace()
    )

    assert result.id == 17
    assert result.attempt_count == 2
    retry.assert_awaited_once_with(session, 17)
    dispatch.assert_called_once_with(
        job_id=17,
        task_id="deliverable-job:17:attempt:2",
    )
    assert "queue" not in dispatch.call_args.kwargs
    session.commit.assert_awaited_once()


def test_public_response_never_serializes_job_internals() -> None:
    payload = routes.DeliverableJobRead.model_validate(_job()).model_dump(mode="json")

    assert set(payload) == {
        "id",
        "kind",
        "title",
        "status",
        "phase",
        "progress",
        "failure_code",
        "artifact_id",
        "workspace_id",
        "thread_id",
        "created_at",
        "updated_at",
    }
