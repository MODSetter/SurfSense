"""Janitor sweep: abandoned working copies pruned across every workspace."""

from __future__ import annotations

import os
import time

import pytest

from app.config import config as app_config
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.janitor import prune_abandoned_working_copies

pytestmark = pytest.mark.unit

DAY = 24 * 60 * 60


@pytest.fixture
def knowledge_root(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ROOT", str(tmp_path))
    return tmp_path


async def _open_copy(workspace_id: str, copy_id: str):
    return await KnowledgeStore.for_workspace(workspace_id).open_working_copy(copy_id)


def _age(path, seconds: float) -> None:
    stamp = time.time() - seconds
    os.utime(path, (stamp, stamp))


async def test_prunes_only_copies_older_than_the_ttl(knowledge_root):
    abandoned = await _open_copy("ws-a", "thread-old")
    fresh = await _open_copy("ws-b", "thread-new")
    _age(abandoned.path, 2 * DAY)

    pruned = await prune_abandoned_working_copies(older_than_seconds=DAY)

    assert pruned == {"ws-a": ["thread-old"]}
    assert not abandoned.path.exists()
    assert fresh.path.exists()


async def test_nothing_to_sweep_when_no_copies_exist(knowledge_root):
    assert await prune_abandoned_working_copies(older_than_seconds=DAY) == {}
