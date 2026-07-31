"""The git-native persistence middleware only builds for flagged cloud workspaces."""

from __future__ import annotations

import pytest

from app.agents.chat.multi_agent_chat.main_agent.middleware.knowledge_store_persistence import (
    KnowledgeStorePersistenceMiddleware,
    build_knowledge_store_persistence_mw,
)
from app.agents.chat.multi_agent_chat.shared.filesystem_selection import FilesystemMode

pytestmark = pytest.mark.unit


def _build(
    mode: FilesystemMode, *, knowledge_store_enabled: bool
) -> KnowledgeStorePersistenceMiddleware | None:
    return build_knowledge_store_persistence_mw(
        filesystem_mode=mode,
        workspace_id=7,
        user_id="1",
        thread_id=42,
        llm=object(),
        knowledge_store_enabled=knowledge_store_enabled,
    )


def test_builds_for_flagged_cloud_workspaces():
    assert isinstance(
        _build(FilesystemMode.CLOUD, knowledge_store_enabled=True),
        KnowledgeStorePersistenceMiddleware,
    )


def test_skipped_when_the_workspace_is_not_flipped():
    assert _build(FilesystemMode.CLOUD, knowledge_store_enabled=False) is None


def test_skipped_outside_cloud_mode():
    assert (
        _build(FilesystemMode.DESKTOP_LOCAL_FOLDER, knowledge_store_enabled=True)
        is None
    )
