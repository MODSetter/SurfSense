"""Cross-process warm-IP exemption cache (Redis-backed, best-effort).

The expensive unit is the reCAPTCHA solve. Within a process the warm pool
(:mod:`fetch`) already solves each sticky IP once; this shares those solves
across the whole worker fleet: a fresh solve on any process **publishes** the
IP's ``GOOGLE_ABUSE_EXEMPTION`` cookies to Redis, and every other process can
**adopt** that IP instead of solving it again. Without this, cost scales with
the number of worker processes; with it, cost scales with the (shared) pool
size.

Best-effort by design: any Redis hiccup disables the layer and every process
falls back to its own local pool — correctness is unchanged, we just pay more
solves. Redis calls run in a worker thread (:func:`asyncio.to_thread`) so they
never block the request loop and don't care which loop the caller is on.

``ponytail:`` the shared store holds only exemptions (the costly artifact), not
per-process render concurrency — global per-IP load is still governed by each
process's local per-IP cap × the number of processes, so size the pool for the
fleet (see ``GOOGLE_SEARCH_WARM_POOL_TARGET``). Full distributed inflight
accounting is the upgrade path if a single shared IP ever gets overloaded.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os

from app.config import config

logger = logging.getLogger(__name__)

_LOG = "[google_search][poolstore]"
_PREFIX = "gsearch:warm:"
# Google's GOOGLE_ABUSE_EXEMPTION outlives this comfortably; a conservative TTL
# just means the fleet re-solves an idle IP occasionally (cheap) and never
# serves a long-dead exemption. Env-tunable.
_TTL_S = int(os.getenv("GOOGLE_SEARCH_EXEMPTION_TTL_S", "3600"))

_client = None
_disabled = False


def _key(proxy: str) -> str:
    return _PREFIX + hashlib.sha1(proxy.encode()).hexdigest()


def _get_client():
    """Lazily build a short-timeout Redis client, disabling on first failure."""
    global _client, _disabled
    if _disabled:
        return None
    if _client is not None:
        return _client
    try:
        import redis

        _client = redis.Redis.from_url(
            config.REDIS_APP_URL, socket_timeout=1, socket_connect_timeout=1
        )
        _client.ping()
    except Exception as e:
        logger.info("%s Redis unavailable; cross-process sharing off: %s", _LOG, e)
        _disabled = True
        _client = None
    return _client


def _publish_sync(proxy: str, cookies: list[dict]) -> None:
    c = _get_client()
    if c is None:
        return
    try:
        c.set(_key(proxy), json.dumps({"proxy": proxy, "cookies": cookies}), ex=_TTL_S)
    except Exception as e:
        logger.debug("%s publish failed: %s", _LOG, e)


def _adopt_sync(exclude: set[str]) -> tuple[str, list[dict]] | None:
    c = _get_client()
    if c is None:
        return None
    try:
        for key in c.scan_iter(match=_PREFIX + "*", count=100):
            raw = c.get(key)
            if not raw:
                continue
            d = json.loads(raw)
            proxy = d.get("proxy")
            if proxy and proxy not in exclude:
                return proxy, d.get("cookies") or []
    except Exception as e:
        logger.debug("%s adopt failed: %s", _LOG, e)
    return None


def _evict_sync(proxy: str) -> None:
    c = _get_client()
    if c is None:
        return
    try:
        c.delete(_key(proxy))
    except Exception as e:
        logger.debug("%s evict failed: %s", _LOG, e)


async def publish(proxy: str, cookies: list[dict]) -> None:
    """Share a freshly-solved IP's exemption with the fleet."""
    await asyncio.to_thread(_publish_sync, proxy, cookies)


async def adopt(exclude: set[str]) -> tuple[str, list[dict]] | None:
    """Return a fleet-warm ``(proxy, cookies)`` not in ``exclude``, or ``None``."""
    return await asyncio.to_thread(_adopt_sync, exclude)


async def evict(proxy: str) -> None:
    """Drop a poisoned (walled) IP so no process adopts its stale exemption."""
    await asyncio.to_thread(_evict_sync, proxy)
