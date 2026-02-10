"""Redis-based connector indexing locks to prevent duplicate sync tasks."""

import redis

from app.config import config

_redis_client: redis.Redis | None = None
LOCK_TTL_SECONDS = config.CONNECTOR_INDEXING_LOCK_TTL_SECONDS


def get_indexing_lock_redis_client() -> redis.Redis:
    """Get or create Redis client for connector indexing locks."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(config.REDIS_APP_URL, decode_responses=True)
    return _redis_client


def _get_connector_lock_key(connector_id: int) -> str:
    """Generate Redis key for a connector indexing lock."""
    return f"indexing:connector_lock:{connector_id}"


def acquire_connector_indexing_lock(connector_id: int) -> bool:
    """Acquire lock for connector indexing. Returns True if acquired."""
    key = _get_connector_lock_key(connector_id)
    return bool(
        get_indexing_lock_redis_client().set(
            key,
            "1",
            nx=True,
            ex=LOCK_TTL_SECONDS,
        )
    )


def release_connector_indexing_lock(connector_id: int) -> None:
    """Release lock for connector indexing."""
    key = _get_connector_lock_key(connector_id)
    get_indexing_lock_redis_client().delete(key)


def is_connector_indexing_locked(connector_id: int) -> bool:
    """Check if connector indexing lock exists."""
    key = _get_connector_lock_key(connector_id)
    return bool(get_indexing_lock_redis_client().exists(key))
