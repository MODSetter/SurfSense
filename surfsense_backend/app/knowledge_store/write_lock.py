"""Cross-process single-writer lock per workspace.

A write never proceeds unserialized: if the lock cannot be acquired (contention
timeout, or Redis unreachable), the caller fails instead of racing.
"""

from __future__ import annotations

from contextlib import asynccontextmanager, suppress

import redis.asyncio as redis
from redis.exceptions import LockError

from app.config import config

# Auto-expiry so a crashed writer can't wedge a workspace; must exceed a commit.
LOCK_TTL_SECONDS = 30.0
# How long a contender waits before giving up.
LOCK_WAIT_SECONDS = 10.0

_client: redis.Redis | None = None


class KnowledgeStoreLockError(RuntimeError):
    """Raised when the workspace write lock could not be acquired."""


def _redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(config.REDIS_APP_URL, decode_responses=True)
    return _client


def _lock_key(workspace_id: int | str) -> str:
    return f"knowledge_store:write_lock:{workspace_id}"


@asynccontextmanager
async def workspace_write_lock(workspace_id: int | str):
    """Hold ``workspace_id``'s single-writer lock for the block."""
    lock = _redis().lock(
        _lock_key(workspace_id),
        timeout=LOCK_TTL_SECONDS,
        blocking=True,
        blocking_timeout=LOCK_WAIT_SECONDS,
    )
    if not await lock.acquire():
        raise KnowledgeStoreLockError(
            f"Could not acquire write lock for workspace {workspace_id} "
            f"within {LOCK_WAIT_SECONDS}s"
        )
    try:
        yield
    finally:
        # Release only our own token; a no-op if the hold already expired.
        with suppress(LockError):
            await lock.release()
