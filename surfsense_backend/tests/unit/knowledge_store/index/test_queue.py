"""Enqueueing must never fail a save whose content is already committed.

The writers call this after the revision is durable, so a broker outage has to
degrade to "the sweep will get it" rather than raise into a save that worked.
That swallow is only safe if the happy path is pinned too — otherwise a typo
here is indistinguishable from a broker being down.
"""

from __future__ import annotations

import pytest

import app.knowledge_store.index.queue as index_queue
from app.config import config as app_config

pytestmark = pytest.mark.unit


@pytest.fixture
def delayed(monkeypatch):
    """Capture the ids handed to the task, without importing celery's broker."""
    calls: list[int] = []

    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    monkeypatch.setattr(
        "app.tasks.celery_tasks.knowledge_store.index_tasks."
        "index_knowledge_store_revision.delay",
        calls.append,
    )
    return calls


def test_a_write_enqueues_its_workspace(delayed):
    index_queue.enqueue_index(7)

    assert delayed == [7]


def test_a_numeric_string_id_still_enqueues(delayed):
    """Callers hand over whatever the request gave them."""
    index_queue.enqueue_index("7")

    assert delayed == [7]


def test_the_kill_switch_stops_enqueueing(delayed, monkeypatch):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", False)

    index_queue.enqueue_index(7)

    assert delayed == []


def test_a_non_numeric_id_is_dropped(delayed):
    """Test-only workspace ids have no worker to serve them."""
    index_queue.enqueue_index("it-abc123")

    assert delayed == []


def test_importing_the_queue_does_not_drag_in_the_converger():
    """A writer's last step must stay cheap to import.

    ``converge`` reaches into the ORM, the indexing pipeline and the agents
    middleware; a convenience re-export in this package's ``__init__`` would put
    all of it on the import path of every save.
    """
    import subprocess
    import sys

    probe = (
        "import sys; import app.knowledge_store.index.queue; "
        "print(any(m.startswith('app.indexing_pipeline') for m in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True
    )

    assert result.stdout.strip().endswith("False")


def test_a_broker_failure_does_not_reach_the_caller(monkeypatch, caplog):
    """The save already committed; the sweep is the backstop."""

    def unreachable(workspace_id):
        raise ConnectionError("broker down")

    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    monkeypatch.setattr(
        "app.tasks.celery_tasks.knowledge_store.index_tasks."
        "index_knowledge_store_revision.delay",
        unreachable,
    )

    index_queue.enqueue_index(7)

    assert "drift sweep" in caplog.text
