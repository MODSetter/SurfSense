"""Redis token-bucket rate limiter for gateway outbound traffic."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

import redis.asyncio as aioredis

from app.config import config
from app.observability.metrics import record_gateway_redis_fallback

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

_redis_client: aioredis.Redis | None = None


@dataclass
class _MemoryBucket:
    tokens: float
    last_refill: float


_memory_buckets: dict[str, _MemoryBucket] = {}
_memory_lock = asyncio.Lock()


def _redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(config.REDIS_APP_URL, decode_responses=True)
    return _redis_client


async def _memory_fallback_acquire(
    scope: str,
    capacity: int,
    refill_per_sec: float,
    consume: float,
) -> int:
    now = time.time()
    async with _memory_lock:
        bucket = _memory_buckets.get(scope)
        if bucket is None:
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
    """Return 0 if allowed, otherwise milliseconds to wait.

    Redis is the primary coordination mechanism.  If Redis is unavailable,
    fall back to per-process memory so the gateway degrades instead of failing
    closed during a short Redis outage.
    """

    redis_key = f"gateway:bucket:{scope}"
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
        logger.warning("Redis rate limiter unavailable; using memory fallback: %s", exc)
        record_gateway_redis_fallback()
        return await _memory_fallback_acquire(scope, capacity, refill_per_sec, consume)


async def wait_for_token(
    scope: str,
    *,
    capacity: int,
    refill_per_sec: float,
    consume: float = 1.0,
) -> int:
    wait_ms = await acquire_token(
        scope,
        capacity=capacity,
        refill_per_sec=refill_per_sec,
        consume=consume,
    )
    if wait_ms > 0:
        await asyncio.sleep(wait_ms / 1000)
    return wait_ms

