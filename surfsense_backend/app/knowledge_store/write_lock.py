"""Cross-process per-workspace locks.

A write never proceeds unserialized: if the lock cannot be acquired (contention
timeout, or Redis unreachable), the caller fails instead of racing. A hold that
outlives its TTL fails just as loudly — exclusivity was lost, never silently.

Indexing takes a *separate* lock. It embeds, so it runs for far longer than a
commit — sharing the write lock would stall agent writes behind embedding calls,
and sizing one TTL for both would either wedge writes or expire mid-rebuild.
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

# Indexing a whole workspace embeds every document, so its ceiling is minutes.
INDEX_LOCK_TTL_SECONDS = 1800.0
# A contender gives up quickly: the holder converges to the current revision
# anyway, and the drift sweep re-drives anything it missed.
INDEX_LOCK_WAIT_SECONDS = 5.0


class KnowledgeStoreLockError(RuntimeError):
    """A workspace lock could not be acquired, or a hold expired mid-block."""


def _lock_key(workspace_id: int | str, purpose: str) -> str:
    return f"knowledge_store:{purpose}:{workspace_id}"


@asynccontextmanager
async def _workspace_lock(
    workspace_id: int | str, *, purpose: str, ttl: float, wait: float
):
    # The client lives and dies with the block rather than being cached: celery
    # runs every task on a fresh event loop, and a pooled connection bound to a
    # closed one fails on the next task. It failed *inside* acquire, after redis
    # had set the key but before the reply was read — leaving the lock held by
    # nobody for its whole TTL. A connection per lock is cheap next to the write
    # it guards.
    client = redis.from_url(config.REDIS_APP_URL, decode_responses=True)
    try:
        lock = client.lock(
            _lock_key(workspace_id, purpose),
            timeout=ttl,
            blocking=True,
            blocking_timeout=wait,
        )
        if not await lock.acquire():
            raise KnowledgeStoreLockError(
                f"Could not acquire {purpose} for workspace {workspace_id} "
                f"within {wait}s"
            )
        try:
            yield
        except BaseException:
            # The block itself failed; a lost hold must not mask that error.
            with suppress(LockError):
                await lock.release()
            raise
        try:
            await lock.release()
        except LockNotOwnedError:
            # The hold outlived the TTL: the work landed, but its tail ran
            # without exclusivity. Fail loudly instead of hiding the race.
            raise KnowledgeStoreLockError(
                f"{purpose} for workspace {workspace_id} expired mid-block "
                f"(hold exceeded the {ttl}s TTL)"
            ) from None
    finally:
        with suppress(Exception):
            await client.aclose()


@asynccontextmanager
async def workspace_write_lock(workspace_id: int | str):
    """Hold ``workspace_id``'s single-writer lock for the block."""
    async with _workspace_lock(
        workspace_id,
        purpose="write_lock",
        ttl=LOCK_TTL_SECONDS,
        wait=LOCK_WAIT_SECONDS,
    ):
        yield


@asynccontextmanager
async def workspace_index_lock(workspace_id: int | str):
    """Hold ``workspace_id``'s single-indexer lock for the block.

    ``ponytail:`` ceiling — a rebuild that outruns the TTL can be joined by a
    second builder; upgrade path is a ``lock.extend()`` heartbeat while indexing.
    """
    async with _workspace_lock(
        workspace_id,
        purpose="index_lock",
        ttl=INDEX_LOCK_TTL_SECONDS,
        wait=INDEX_LOCK_WAIT_SECONDS,
    ):
        yield
