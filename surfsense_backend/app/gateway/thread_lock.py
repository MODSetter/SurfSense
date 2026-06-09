"""Redis-backed distributed locks for gateway conversation turns."""

from __future__ import annotations

import logging

import redis

from app.config import config
from app.observability.metrics import record_gateway_thread_lock_contention

logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None


def _redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(config.REDIS_APP_URL, decode_responses=True)
    return _redis_client


def _lock_key(thread_id: int) -> str:
    return f"gateway:thread_lock:{thread_id}"


def acquire_thread_lock(thread_id: int, ttl: int = 60) -> bool:
    acquired = bool(_redis().set(_lock_key(thread_id), "1", nx=True, ex=ttl))
    if not acquired:
        record_gateway_thread_lock_contention()
    return acquired


def release_thread_lock(thread_id: int) -> None:
    try:
        _redis().delete(_lock_key(thread_id))
    except redis.RedisError as exc:
        logger.warning(
            "Failed to release gateway thread lock for %s: %s", thread_id, exc
        )
