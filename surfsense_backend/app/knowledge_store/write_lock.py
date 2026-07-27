"""Single-writer serialization for a workspace's store.

The backend runs as many OS processes (API workers, Celery workers) that share
one on-disk repo, so an in-process lock is not enough. This holds a Redis lock
per workspace: writers queue briefly under contention, and a write never
proceeds unserialized — if the lock cannot be taken (including Redis being
unreachable), the caller fails rather than racing another writer.
"""

from __future__ import annotations

from contextlib import asynccontextmanager, suppress

import redis.asyncio as redis
from redis.exceptions import LockError

from app.config import config

# Lock auto-expires so a crashed writer can't wedge a workspace forever. It must
# comfortably exceed a normal commit; a stuck holder is recovered after this.
LOCK_TTL_SECONDS = 30.0
# How long a contending writer waits in line before giving up.
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
    """Hold the single-writer lock for ``workspace_id`` for the block's duration.

    The lock is token-owned: release only clears our own hold, so an expired
    lock reclaimed by another writer is never dropped by us.
    """
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
        # If our hold already expired (and was possibly reclaimed), the token
        # check makes release a no-op rather than dropping another writer's lock.
        with suppress(LockError):
            await lock.release()
