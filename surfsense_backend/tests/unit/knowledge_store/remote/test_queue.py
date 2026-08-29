"""enqueue_push must never fail a save whose content is already committed."""

from __future__ import annotations

import pytest

import app.knowledge_store.remote.queue as remote_queue
from app.config import config as app_config

pytestmark = pytest.mark.unit


@pytest.fixture
def delayed(monkeypatch):
    calls: list[int] = []
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    monkeypatch.setattr(
        "app.tasks.celery_tasks.knowledge_store.push_task."
        "push_knowledge_store_revision.delay",
        calls.append,
    )
    return calls


def test_a_write_enqueues_its_workspace(delayed):
    remote_queue.enqueue_push(7)
    assert delayed == [7]


def test_the_kill_switch_stops_enqueueing(delayed, monkeypatch):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", False)
    remote_queue.enqueue_push(7)
    assert delayed == []


def test_a_non_numeric_id_is_dropped(delayed):
    remote_queue.enqueue_push("it-abc123")
    assert delayed == []


def test_importing_the_queue_does_not_drag_in_forges():
    import subprocess
    import sys

    probe = (
        "import sys; import app.knowledge_store.remote.queue; "
        "print(any('app.knowledge_store.remote.forges' in m for m in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip().endswith("False")


def test_a_broker_failure_does_not_reach_the_caller(monkeypatch, caplog):
    def unreachable(workspace_id):
        raise ConnectionError("broker down")

    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    monkeypatch.setattr(
        "app.tasks.celery_tasks.knowledge_store.push_task."
        "push_knowledge_store_revision.delay",
        unreachable,
    )
    remote_queue.enqueue_push(7)
    assert "drift sweep" in caplog.text
