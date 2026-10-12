"""Warm IPs shared across copies of the host, in Redis: a solve on one copy warms that IP for all.

The expensive unit is the reCAPTCHA solve. Each copy's warm pool (:mod:`fetch`)
solves each sticky IP once; this shares those solves: a fresh solve **publishes**
the IP's ``GOOGLE_ABUSE_EXEMPTION`` cookies, and any other copy can **adopt**
that IP instead of solving again, so cost tracks the shared pool, not the copies.

Best-effort: without ``REDIS_URL``, or with Redis unreachable, every call is a
no-op and each copy keeps its own pool. Correctness is unchanged; we pay more
solves. The stored proxy URLs carry the vendor's credentials, as the copies'
environment does.

``ponytail:`` only exemptions are shared, not each IP's renders in flight, so
global per-IP load is each copy's cap times the copies: size the pool for them.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os

import redis.asyncio as redis

logger = logging.getLogger(__name__)

_LOG = "[google_search][poolstore]"
_PREFIX = "surfsense:google-search:warm:"
# Google's GOOGLE_ABUSE_EXEMPTION outlives this comfortably; a conservative TTL
# just means the fleet re-solves an idle IP occasionally (cheap) and never
# serves a long-dead exemption. Env-tunable.
_TTL_S = int(os.getenv("GOOGLE_SEARCH_EXEMPTION_TTL_S", "3600"))

_client: redis.Redis | None = None
_disabled = False


def _key(proxy: str) -> str:
    return _PREFIX + hashlib.sha1(proxy.encode()).hexdigest()


def _get_client() -> redis.Redis | None:
    """A short-timeout client for REDIS_URL, made once; None without one."""
    global _client, _disabled
    if _disabled:
        return None
    if _client is None:
        url = os.environ.get("REDIS_URL")
        if not url:
            _disabled = True
            return None
        _client = redis.from_url(url, socket_timeout=1, socket_connect_timeout=1)
    return _client


async def publish(proxy: str, cookies: list[dict]) -> None:
    """Share a freshly-solved IP's exemption with the fleet."""
    client = _get_client()
    if client is None:
        return
    try:
        payload = json.dumps({"proxy": proxy, "cookies": cookies})
        await client.set(_key(proxy), payload, ex=_TTL_S)
    except redis.RedisError as e:
        logger.debug("%s publish failed: %s", _LOG, e)


async def adopt(exclude: set[str]) -> tuple[str, list[dict]] | None:
    """Return a fleet-warm ``(proxy, cookies)`` not in ``exclude``, or ``None``."""
    client = _get_client()
    if client is None:
        return None
    try:
        async for key in client.scan_iter(match=_PREFIX + "*", count=100):
            raw = await client.get(key)
            if not raw:
                continue
            stored = json.loads(raw)
            proxy = stored.get("proxy")
            if proxy and proxy not in exclude:
                return proxy, stored.get("cookies") or []
    except redis.RedisError as e:
        logger.debug("%s adopt failed: %s", _LOG, e)
    return None


async def evict(proxy: str) -> None:
    """Drop a poisoned (walled) IP so no process adopts its stale exemption."""
    client = _get_client()
    if client is None:
        return
    try:
        await client.delete(_key(proxy))
    except redis.RedisError as e:
        logger.debug("%s evict failed: %s", _LOG, e)
