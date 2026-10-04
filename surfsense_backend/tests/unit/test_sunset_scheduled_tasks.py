"""Hosted sunset behavior for recurring user-work Celery tasks."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.automations.triggers.builtin.schedule import selector as automation_selector
from app.tasks.celery_tasks import schedule_checker_task
from app.tasks.celery_tasks.knowledge_store import drift_monitor_task, index_tasks

pytestmark = pytest.mark.unit

_SCHEDULED_TASKS = (
    pytest.param(
        schedule_checker_task,
        "check_periodic_schedules_task",
        "run_async_celery_task",
        None,
        id="connector-indexing",
    ),
    pytest.param(
        automation_selector,
        "automation_schedule_select",
        "run_async_celery_task",
        None,
        id="scheduled-automations",
    ),
    pytest.param(
        index_tasks,
        "reindex_drifted_workspaces",
        "run_async_celery_task",
        0,
        id="knowledge-store-reindex",
    ),
    pytest.param(
        drift_monitor_task,
        "check_knowledge_store_drift",
        "asyncio.run",
        {},
        id="knowledge-store-drift-check",
    ),
)


def _patch_runner(monkeypatch, task_module, runner_name: str):
    if hasattr(task_module, "load_knowledge_store_settings"):
        monkeypatch.setattr(
            task_module,
            "load_knowledge_store_settings",
            lambda: SimpleNamespace(enabled=True),
        )
    runner = Mock(return_value=object())
    if runner_name == "asyncio.run":
        monkeypatch.setattr(task_module.asyncio, "run", runner)
    else:
        monkeypatch.setattr(task_module, runner_name, runner)
    return runner


@pytest.mark.parametrize(
    ("task_module", "task_name", "runner_name", "skipped_result"),
    _SCHEDULED_TASKS,
)
def test_hosted_user_work_is_skipped_during_sunset(
    monkeypatch, task_module, task_name, runner_name, skipped_result
):
    monkeypatch.setenv("DEPLOYMENT_MODE", "cloud")
    monkeypatch.setenv("SUNSET_MODE", "1")
    runner = _patch_runner(monkeypatch, task_module, runner_name)

    result = getattr(task_module, task_name)()

    assert result == skipped_result
    runner.assert_not_called()


@pytest.mark.parametrize(
    ("deployment_mode", "sunset_mode"),
    [
        pytest.param("cloud", "0", id="hosted-sunset-off"),
        pytest.param("self-hosted", "1", id="self-hosted-ignores-sunset"),
    ],
)
@pytest.mark.parametrize(
    ("task_module", "task_name", "runner_name", "_skipped_result"),
    _SCHEDULED_TASKS,
)
def test_hosted_user_work_keeps_running_outside_sunset(
    monkeypatch,
    deployment_mode,
    sunset_mode,
    task_module,
    task_name,
    runner_name,
    _skipped_result,
):
    monkeypatch.setenv("DEPLOYMENT_MODE", deployment_mode)
    monkeypatch.setenv("SUNSET_MODE", sunset_mode)
    runner = _patch_runner(monkeypatch, task_module, runner_name)

    result = getattr(task_module, task_name)()

    assert result is runner.return_value
    assert result != _skipped_result
    runner.assert_called_once()
