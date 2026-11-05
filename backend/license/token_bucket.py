"""A token bucket in Redis, shared by every copy of the backend, falling back to memory.

A Redis outage degrades to per-process limits rather than refusing every request.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass

import redis.asyncio as aioredis

from license.settings import config

logger = logging.getLogger(__name__)

_TOKEN_BUCKET_LUA = """
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local consume = tonumber(ARGV[4])

local bucket = redis.call('HMGET', KEYS[1], 'tokens', 'last_refill')
local tokens = tonumber(bucket[1]) or capacity
local last_refill = tonumber(bucket[2]) or now

local elapsed = math.max(0, now - last_refill)
tokens = math.min(capacity, tokens + (elapsed * refill_rate))

if tokens >= consume then
    tokens = tokens - consume
    redis.call('HMSET', KEYS[1], 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', KEYS[1], 3600)
    return 0
else
    redis.call('HMSET', KEYS[1], 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', KEYS[1], 3600)
    local needed = consume - tokens
    return math.ceil((needed / refill_rate) * 1000)
end
"""

# A bucket idle an hour is full again, since every limit refills per hour, so
# forgetting it changes no answer; Redis expires its keys after the same hour.
_IDLE_SECONDS = 3600.0
# While the portal is served, idle buckets go within this long of their hour, even
# when no request comes after them.
_SWEEP_SECONDS = 60.0
# Bounds a flood of new addresses: at about 260 bytes a bucket with its name,
# the map stays under 30 MB.
_MAX_MEMORY_BUCKETS = 100_000

_redis_client: aioredis.Redis | None = None


@dataclass
class _MemoryBucket:
    tokens: float
    last_refill: float


# Least recently refilled first: each refill moves its bucket to the end.
_memory_buckets: dict[str, _MemoryBucket] = {}
_memory_lock = asyncio.Lock()


def _redis() -> aioredis.Redis:
    global _redis_client
    if not config.REDIS_URL:
        raise OSError("REDIS_URL is not set")
    if _redis_client is None:
        _redis_client = aioredis.from_url(config.REDIS_URL, decode_responses=True)
    return _redis_client


def _forget_idle(now: float) -> None:
    """Drop the buckets idle an hour; a sweep costs only the buckets it drops."""
    idle = []
    # Oldest refill first, so the first bucket still in use ends the sweep.
    for scope, bucket in _memory_buckets.items():
        if now - bucket.last_refill < _IDLE_SECONDS:
            break
        idle.append(scope)
    for scope in idle:
        del _memory_buckets[scope]


async def _sweep_every_minute() -> None:
    while True:
        await asyncio.sleep(_SWEEP_SECONDS)
        async with _memory_lock:
            _forget_idle(time.time())


@asynccontextmanager
async def forgetting_idle_buckets(_: object) -> AsyncIterator[None]:
    """The license portal's lifespan: idle memory buckets are swept every minute while it
    is served, so a caller's counts go an hour after its last request with none after it."""
    sweeper = asyncio.create_task(_sweep_every_minute())
    try:
        yield
    finally:
        sweeper.cancel()
        with suppress(asyncio.CancelledError):
            await sweeper


async def _memory_fallback_acquire(
    scope: str,
    capacity: int,
    refill_per_sec: float,
    consume: float,
) -> int:
    now = time.time()
    async with _memory_lock:
        _forget_idle(now)
        bucket = _memory_buckets.pop(scope, None)
        if bucket is None:
            if len(_memory_buckets) >= _MAX_MEMORY_BUCKETS:
                del _memory_buckets[next(iter(_memory_buckets))]
            bucket = _MemoryBucket(tokens=float(capacity), last_refill=now)
        _memory_buckets[scope] = bucket

        elapsed = max(0.0, now - bucket.last_refill)
        bucket.tokens = min(float(capacity), bucket.tokens + elapsed * refill_per_sec)
        bucket.last_refill = now

        if bucket.tokens >= consume:
            bucket.tokens -= consume
            return 0

        needed = consume - bucket.tokens
        return int((needed / refill_per_sec) * 1000) if refill_per_sec > 0 else 1000


async def acquire_token(
    scope: str,
    *,
    capacity: int,
    refill_per_sec: float,
    consume: float = 1.0,
) -> int:
    """0 when allowed, otherwise the milliseconds to wait."""
    redis_key = f"bucket:{scope}"
    try:
        wait_ms = await _redis().eval(
            _TOKEN_BUCKET_LUA,
            1,
            redis_key,
            capacity,
            refill_per_sec,
            time.time(),
            consume,
        )
        return int(wait_ms)
    except (aioredis.RedisError, OSError) as exc:
        if config.REDIS_URL:
            logger.warning(
                "Redis rate limiter unavailable; using memory fallback: %s", exc
            )
        return await _memory_fallback_acquire(scope, capacity, refill_per_sec, consume)
