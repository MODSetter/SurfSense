"""Per-workspace rate limit for the capability doors (05).

A secondary abuse guard; the credit meter-gate (03c) is the primary control.
Fixed-window over Redis (shared across workers) with a per-worker in-memory
fallback when Redis is unavailable — mirroring the auth-endpoint limiter.
"""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request, status

from app.config import config

CAPABILITY_RATE_LIMIT_PER_MINUTE = 120
_WINDOW_SECONDS = 60
_KEY_PREFIX = "surfsense:capability_rate_limit"

_redis = None
_memory: dict[str, list[float]] = defaultdict(list)
_memory_lock = Lock()


def _redis_client():
    global _redis
    if _redis is None:
        import redis

        _redis = redis.from_url(config.REDIS_APP_URL, decode_responses=True)
    return _redis


def _incr_memory(key: str, window_seconds: int) -> int:
    now = time.monotonic()
    with _memory_lock:
        hits = [t for t in _memory[key] if now - t < window_seconds]
        hits.append(now)
        _memory[key] = hits
        return len(hits)


def _incr(key: str, window_seconds: int) -> int:
    """Increment the window counter for ``key`` and return the new count."""
    try:
        client = _redis_client()
        count = int(client.incr(key))
        if count == 1:
            client.expire(key, window_seconds)
        return count
    except Exception:
        return _incr_memory(key, window_seconds)


async def enforce_capability_rate_limit(request: Request) -> None:
    """Cap requests per workspace per minute; raise 429 when exceeded."""
    workspace_id = request.path_params.get("workspace_id")
    count = _incr(f"{_KEY_PREFIX}:{workspace_id}", _WINDOW_SECONDS)
    if count > CAPABILITY_RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded for this workspace. Try again shortly.",
        )
