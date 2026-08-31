"""After a durable revision, index and folder sync are both asked for."""

from __future__ import annotations

import pytest

from app.knowledge_store import KnowledgeStore

pytestmark = pytest.mark.unit


def test_after_record_enqueues_index_and_sync(monkeypatch):
    calls: list[tuple[str, int | str]] = []
    monkeypatch.setattr(
        "app.knowledge_store.index.queue.enqueue_index",
        lambda workspace_id: calls.append(("index", workspace_id)),
    )
    monkeypatch.setattr(
        "app.knowledge_store.remote.queue.enqueue_sync",
        lambda workspace_id: calls.append(("sync", workspace_id)),
    )
    KnowledgeStore.for_workspace(7)._enqueue_after_revision()
    assert calls == [("index", 7), ("sync", 7)]


def test_mark_synced_stamps_the_card_marker():
    from types import SimpleNamespace

    from app.knowledge_store.remote.facade import _mark_synced

    row = SimpleNamespace(
        last_pushed_revision=None, last_pushed_at=None, last_push_error="boom"
    )
    _mark_synced(row, "rev123")
    assert row.last_pushed_revision == "rev123"
    assert row.last_pushed_at is not None
    assert row.last_push_error is None


def test_mark_synced_ignores_an_empty_revision():
    from types import SimpleNamespace

    from app.knowledge_store.remote.facade import _mark_synced

    row = SimpleNamespace(
        last_pushed_revision="old", last_pushed_at="t", last_push_error=None
    )
    _mark_synced(row, None)
    assert row.last_pushed_revision == "old"
