"""After a durable revision, index and push are both asked for."""

from __future__ import annotations

import pytest

from app.knowledge_store import KnowledgeStore

pytestmark = pytest.mark.unit


def test_after_record_enqueues_index_and_push(monkeypatch):
    calls: list[tuple[str, int | str]] = []
    monkeypatch.setattr(
        "app.knowledge_store.index.queue.enqueue_index",
        lambda workspace_id: calls.append(("index", workspace_id)),
    )
    monkeypatch.setattr(
        "app.knowledge_store.remote.queue.enqueue_push",
        lambda workspace_id: calls.append(("push", workspace_id)),
    )
    KnowledgeStore.for_workspace(7)._enqueue_after_revision()
    assert calls == [("index", 7), ("push", 7)]
