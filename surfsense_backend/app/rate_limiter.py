"""Shared SlowAPI limiter instance used by app.py and route modules."""

from limits.storage import MemoryStorage
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import config

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=config.REDIS_APP_URL,
    default_limits=["1024/minute"],
    in_memory_fallback_enabled=True,
    in_memory_fallback=[MemoryStorage()],
)
