"""Git-native write tools must leave nothing for the legacy commit to redo.

Both write paths coexist until the Phase 5 cut. On a flipped workspace the git
backend owns the write and ``kb_persistence`` must find nothing staged: it turns
``dirty_paths`` into Postgres documents, so a tool that stages anyway gets the
same write recorded twice — once as a revision, once as a legacy document git
never hears about. The four pure-staging tools (``mkdir``, ``move_file``,
``rm``, ``rmdir``) already branch on the backend; these pin the two that stage
as a side effect of a successful write.

The backend is the real one on a temp repo — only the storage root is
redirected.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.agents.chat.multi_agent_chat.shared.filesystem_selection import (
    FilesystemMode,
    FilesystemSelection,
)
from app.agents.chat.multi_agent_chat.shared.middleware.filesystem import (
    build_filesystem_mw,
)
from app.agents.chat.multi_agent_chat.shared.middleware.filesystem.backends.resolver import (
    build_backend_resolver,
)
from app.config import config as app_config

pytestmark = pytest.mark.unit

WORKSPACE_ID = 3
NOTE = "/documents/note.md"


@pytest.fixture
def knowledge_root(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ROOT", str(tmp_path))
    return tmp_path


def _middleware(*, workspace_id: int | None, knowledge_store_enabled: bool):
    selection = FilesystemSelection(mode=FilesystemMode.CLOUD)
    resolver = build_backend_resolver(
        selection,
        workspace_id=workspace_id,
        knowledge_store_enabled=knowledge_store_enabled,
    )
    return build_filesystem_mw(
        backend_resolver=resolver,
        filesystem_mode=FilesystemMode.CLOUD,
        workspace_id=workspace_id,
        user_id="00000000-0000-0000-0000-000000000001",
        thread_id=1,
    )


def _tool(mw, name: str):
    return next(t for t in mw.tools if t.name == name)


def _runtime(state: dict[str, Any] | None = None):
    state = state or {}
    state.setdefault("cwd", "/documents")
    return SimpleNamespace(
        state=state,
        tool_call_id="tc-1",
        config={"configurable": {"thread_id": 1}},
    )


async def test_write_file_stages_nothing_for_the_legacy_commit(knowledge_root):
    mw = _middleware(workspace_id=WORKSPACE_ID, knowledge_store_enabled=True)

    result = await _tool(mw, "write_file").coroutine(NOTE, "hello", runtime=_runtime())

    assert "dirty_paths" not in result.update


async def test_edit_file_stages_nothing_for_the_legacy_commit(knowledge_root):
    mw = _middleware(workspace_id=WORKSPACE_ID, knowledge_store_enabled=True)
    runtime = _runtime()
    await _tool(mw, "write_file").coroutine(NOTE, "hello", runtime=runtime)

    result = await _tool(mw, "edit_file").coroutine(
        NOTE, "hello", "goodbye", runtime=runtime
    )

    assert "dirty_paths" not in result.update


async def test_a_workspace_still_on_the_old_path_keeps_staging(knowledge_root):
    """The guard must not disarm the legacy commit for unflipped workspaces."""
    mw = _middleware(workspace_id=None, knowledge_store_enabled=False)

    result = await _tool(mw, "write_file").coroutine(NOTE, "hello", runtime=_runtime())

    assert result.update["dirty_paths"] == [NOTE]
