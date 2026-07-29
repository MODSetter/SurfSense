"""workspace_write_lock over real Redis: one writer per workspace, fail over race."""

from __future__ import annotations

import asyncio

import pytest

import app.knowledge_store.write_lock as write_lock
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


async def test_hold_outliving_the_ttl_fails_loudly(workspace_id, monkeypatch):
    monkeypatch.setattr(write_lock, "LOCK_TTL_SECONDS", 0.1)
    with pytest.raises(KnowledgeStoreLockError, match="expired mid-write"):
        async with workspace_write_lock(workspace_id):
            await asyncio.sleep(0.3)


async def test_scope_error_is_not_masked_by_an_expired_hold(workspace_id, monkeypatch):
    monkeypatch.setattr(write_lock, "LOCK_TTL_SECONDS", 0.1)
    with pytest.raises(RuntimeError, match="boom"):
        async with workspace_write_lock(workspace_id):
            await asyncio.sleep(0.3)
            raise RuntimeError("boom")
