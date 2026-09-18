"""Shared SlowAPI limiter instance used by app.py and route modules."""

from __future__ import annotations

from slowapi import Limiter
from starlette.requests import Request

from app.config import config


def get_real_client_ip(request: Request) -> str:
    """Extract the real client IP behind Cloudflare / reverse proxies.

    Priority: CF-Connecting-IP > X-Real-IP > X-Forwarded-For (first entry) > socket peer.
    """
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


_DEFAULT_LIMIT = "1024/minute"

limiter = Limiter(
    key_func=get_real_client_ip,
    storage_uri=config.REDIS_APP_URL,
    default_limits=[_DEFAULT_LIMIT],
    in_memory_fallback_enabled=True,
    in_memory_fallback=[_DEFAULT_LIMIT],
)
