"""The git-native persistence middleware only builds for flagged cloud workspaces."""

from __future__ import annotations

import pytest

from app.agents.chat.multi_agent_chat.main_agent.middleware.knowledge_store_persistence import (
    KnowledgeStorePersistenceMiddleware,
    build_knowledge_store_persistence_mw,
)
from app.agents.chat.multi_agent_chat.shared.filesystem_selection import FilesystemMode
from app.config import config as app_config

pytestmark = pytest.mark.unit


def _build(mode: FilesystemMode) -> KnowledgeStorePersistenceMiddleware | None:
    return build_knowledge_store_persistence_mw(
        filesystem_mode=mode,
        workspace_id=7,
        user_id="1",
        thread_id=42,
        llm=object(),
    )


def test_builds_for_flagged_cloud_workspaces(monkeypatch, tmp_path):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ROOT", str(tmp_path))
    assert isinstance(_build(FilesystemMode.CLOUD), KnowledgeStorePersistenceMiddleware)


def test_skipped_when_the_flag_is_off(monkeypatch):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", False)
    assert _build(FilesystemMode.CLOUD) is None


def test_skipped_outside_cloud_mode(monkeypatch, tmp_path):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ROOT", str(tmp_path))
    assert _build(FilesystemMode.DESKTOP_LOCAL_FOLDER) is None
