"""knowledge_store_enabled_for: master switch AND workspace flip, cached."""

from __future__ import annotations

import pytest

import app.knowledge_store.settings as settings
from app.config import config as app_config
from app.knowledge_store.settings import knowledge_store_enabled_for

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def fresh_cache():
    settings._flag_cache.clear()
    yield
    settings._flag_cache.clear()


@pytest.fixture
def workspace_flag(monkeypatch):
    """Fake only the DB read; returns a dict the test mutates to 'flip'."""
    flags: dict[int, bool] = {}
    reads = {"count": 0}

    async def read(workspace_id: int) -> bool:
        reads["count"] += 1
        return flags.get(workspace_id, False)

    monkeypatch.setattr(settings, "_read_workspace_flag", read)
    return flags, reads


async def test_global_kill_switch_wins(monkeypatch, workspace_flag):
    flags, reads = workspace_flag
    flags[1] = True
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", False)

    assert await knowledge_store_enabled_for(1) is False
    assert reads["count"] == 0  # off means off, no DB read


async def test_requires_both_switches(monkeypatch, workspace_flag):
    flags, _ = workspace_flag
    flags[1] = True
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)

    assert await knowledge_store_enabled_for(1) is True
    assert await knowledge_store_enabled_for(2) is False  # not flipped


async def test_workspace_flag_is_cached(monkeypatch, workspace_flag):
    flags, reads = workspace_flag
    flags[1] = True
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)

    assert await knowledge_store_enabled_for(1) is True
    assert await knowledge_store_enabled_for(1) is True
    assert reads["count"] == 1


async def test_flip_propagates_after_ttl(monkeypatch, workspace_flag):
    flags, _ = workspace_flag
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    monkeypatch.setattr(settings, "_FLAG_TTL_SECONDS", 0.0)

    assert await knowledge_store_enabled_for(1) is False
    flags[1] = True
    assert await knowledge_store_enabled_for(1) is True
