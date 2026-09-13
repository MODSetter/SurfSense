"""Short Redis locks for the license routes.

These replace the ``pg_advisory_xact_lock`` the table-backed build used. With
Keygen as the only system of record there is no row to take a lock on, and no
transaction to scope one to.

A lock narrows a read-then-create window; it is not a unique constraint. The
accepted consequence is written down in
``plans/community-local/portal/01-license-routes.md``: a race inside the TTL
can mint a duplicate license. It is bounded, visible in the Keygen dashboard,
and the buyer gets a working file either way.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as aioredis

from app.config import config

logger = logging.getLogger(__name__)

_LOCK_TTL_SECONDS = 30
_redis_client: aioredis.Redis | None = None

_RELEASE_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""


def _redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(config.REDIS_APP_URL, decode_responses=True)
    return _redis_client


@asynccontextmanager
async def license_lock(
    key: str,
    *,
    ttl_seconds: int = _LOCK_TTL_SECONDS,
) -> AsyncIterator[bool]:
    """Hold ``key`` for the block, yielding whether the lock was acquired.

    Yields ``True`` when Redis is unreachable as well: the Keygen lookup that
    follows is the real idempotency check, so failing closed here would take
    purchases down for a Redis blip without making anything safer.
    """
    redis_key = f"license:lock:{key}"
    token = uuid.uuid4().hex
    acquired = False
    try:
        acquired = bool(await _redis().set(redis_key, token, nx=True, ex=ttl_seconds))
        yield acquired
    except (aioredis.RedisError, OSError) as exc:
        logger.warning(
            "Redis unavailable for license lock %s; proceeding unlocked: %s", key, exc
        )
        yield True
        return
    finally:
        if acquired:
            try:
                await _redis().eval(_RELEASE_LUA, 1, redis_key, token)
            except (aioredis.RedisError, OSError):
                # The TTL will clear it; a stuck lock only delays a retry.
                logger.debug("Could not release license lock %s", key, exc_info=True)
