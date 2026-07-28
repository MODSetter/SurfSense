"""workspace_write_lock over real Redis: one writer per workspace, fail over race."""

from __future__ import annotations

import pytest

from app.knowledge_store.write_lock import (
    KnowledgeStoreLockError,
    workspace_write_lock,
)

pytestmark = pytest.mark.integration


async def test_serializes_writers_of_one_workspace(workspace_id, short_lock_wait):
    async with workspace_write_lock(workspace_id):
        with pytest.raises(KnowledgeStoreLockError):
            async with workspace_write_lock(workspace_id):
                pass


async def test_workspaces_do_not_contend(workspace_id):
    async with workspace_write_lock(workspace_id):
        entered = False
        async with workspace_write_lock(f"{workspace_id}-other"):
            entered = True
        assert entered


async def test_lock_is_released_on_scope_exit(workspace_id, short_lock_wait):
    async with workspace_write_lock(workspace_id):
        pass
    # A second writer succeeds because the first hold was released.
    async with workspace_write_lock(workspace_id):
        pass


async def test_lock_is_released_when_the_scope_raises(workspace_id, short_lock_wait):
    with pytest.raises(RuntimeError):
        async with workspace_write_lock(workspace_id):
            raise RuntimeError("boom")

    async with workspace_write_lock(workspace_id):
        pass
