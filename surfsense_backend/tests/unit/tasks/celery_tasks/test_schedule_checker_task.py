"""Unit tests for the periodic schedule checker's connector-to-task dispatch."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.db import SearchSourceConnectorType
from app.tasks.celery_tasks import schedule_checker_task

pytestmark = pytest.mark.unit


class _FakeScalars:
    def __init__(self, connectors):
        self._connectors = connectors

    def all(self):
        return self._connectors


class _FakeDueConnectorsResult:
    def __init__(self, connectors):
        self._connectors = connectors

    def scalars(self):
        return _FakeScalars(self._connectors)


class _FakeEmptyResult:
    def first(self):
        return None


class _FakeSession:
    """Session stub: first execute() returns due connectors, later ones no rows."""

    def __init__(self, connectors):
        self._results = [_FakeDueConnectorsResult(connectors)]
        self.commits = 0

    async def execute(self, _query):
        if self._results:
            return self._results.pop(0)
        return _FakeEmptyResult()

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        pass


def _due_connector(connector_type: SearchSourceConnectorType) -> SimpleNamespace:
    return SimpleNamespace(
        id=42,
        connector_type=connector_type,
        search_space_id=7,
        user_id="00000000-0000-0000-0000-000000000001",
        config={},
        periodic_indexing_enabled=True,
        indexing_frequency_minutes=60,
        next_scheduled_at=datetime.now(UTC) - timedelta(minutes=5),
    )


async def _run_checker(monkeypatch: pytest.MonkeyPatch, connector: SimpleNamespace):
    session = _FakeSession([connector])

    @asynccontextmanager
    async def _session_ctx():
        yield session

    monkeypatch.setattr(
        schedule_checker_task, "get_celery_session_maker", lambda: _session_ctx
    )
    monkeypatch.setattr(
        schedule_checker_task, "is_connector_indexing_locked", lambda _id: False
    )
    await schedule_checker_task._check_and_trigger_schedules()
    return session


@pytest.mark.asyncio
async def test_due_bookstack_connector_dispatches_indexing_task(monkeypatch):
    """A due BookStack connector must dispatch index_bookstack_pages_task.

    Regression test for the connector type missing from the scheduler's
    task_map, which made periodic BookStack syncs silently no-op with only a
    "No task found" warning.
    """
    from app.tasks.celery_tasks import connector_tasks

    task_mock = MagicMock()
    monkeypatch.setattr(connector_tasks, "index_bookstack_pages_task", task_mock)

    connector = _due_connector(SearchSourceConnectorType.BOOKSTACK_CONNECTOR)
    session = await _run_checker(monkeypatch, connector)

    task_mock.delay.assert_called_once_with(
        connector.id,
        connector.search_space_id,
        str(connector.user_id),
        None,
        None,
    )
    # The next run must be rescheduled, otherwise the connector stays "due"
    # and is re-examined every minute.
    assert connector.next_scheduled_at > datetime.now(UTC)
    assert session.commits == 1


@pytest.mark.asyncio
async def test_unmapped_connector_type_does_not_dispatch(monkeypatch):
    """Connector types absent from task_map are skipped without dispatching."""
    from app.tasks.celery_tasks import connector_tasks

    task_mock = MagicMock()
    monkeypatch.setattr(connector_tasks, "index_bookstack_pages_task", task_mock)

    connector = _due_connector(SearchSourceConnectorType.TAVILY_API)
    session = await _run_checker(monkeypatch, connector)

    task_mock.delay.assert_not_called()
    assert session.commits == 0
