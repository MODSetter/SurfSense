"""Cross-process single-writer lock per workspace.

A write never proceeds unserialized: if the lock cannot be acquired (contention
timeout, or Redis unreachable), the caller fails instead of racing. A hold that
outlives its TTL fails just as loudly — exclusivity was lost, never silently.
"""

from __future__ import annotations

from contextlib import asynccontextmanager, suppress

import redis.asyncio as redis
from redis.exceptions import LockError, LockNotOwnedError

from app.config import config

# Auto-expiry so a crashed writer can't wedge a workspace; must outlast a write.
LOCK_TTL_SECONDS = 30.0
# How long a contender waits before giving up.
LOCK_WAIT_SECONDS = 10.0

_client: redis.Redis | None = None


class KnowledgeStoreLockError(RuntimeError):
    """The write lock could not be acquired, or a hold expired mid-write."""


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
    except BaseException:
        # The write itself failed; a lost hold must not mask that error.
        with suppress(LockError):
            await lock.release()
        raise
    try:
        await lock.release()
    except LockNotOwnedError:
        # The hold outlived the TTL: the write landed, but its tail ran
        # without exclusivity. Fail loudly instead of hiding the race.
        raise KnowledgeStoreLockError(
            f"Write lock for workspace {workspace_id} expired mid-write "
            f"(hold exceeded the {LOCK_TTL_SECONDS}s TTL)"
        ) from None
