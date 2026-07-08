"""Rotate-on-block sticky proxy session, bound per-flow via a ContextVar.

Reusing one keep-alive connection pins a single residential exit IP so the
warmed cookie jar (``ttwid``/``msToken``, bound to that IP) stays valid across
the warm-up and every subsequent fetch. Ported from the Reddit sibling; the
TikTok-specific warm-up lives in :mod:`client`.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from contextlib import asynccontextmanager, suppress
from contextvars import ContextVar
from typing import Any

from scrapling.fetchers import FetcherSession

from app.utils.proxy import get_proxy_url

logger = logging.getLogger(__name__)

# Pace each sticky IP so a fast exit can't burst past TikTok's per-IP threshold.
_MIN_INTERVAL_S = 0.5
_PACE_JITTER_S = 0.25
# A healthy fetch lands in ~1-2s; cap a dead IP at one bounded wait before it
# falls through to a rotation.
_REQUEST_TIMEOUT_S = 15.0

_current_session: ContextVar[_RotatingSession | None] = ContextVar(
    "tiktok_proxy_session", default=None
)


class _RotatingSession:
    """Owns one live ``FetcherSession`` (sticky IP); ``rotate()`` swaps the IP.

    Used sequentially within a single flow (never shared across concurrent
    tasks), so no locking is needed. ``session`` is ``None`` only when no proxy
    is configured.
    """

    def __init__(self) -> None:
        self._cm: Any | None = None
        self.session: Any | None = None
        self.rotations = 0
        self.warmed = False
        self._last_at = 0.0

    async def _open(self) -> None:
        proxy = get_proxy_url()
        self.warmed = False
        if proxy is None:
            self._cm = self.session = None
            return
        self._cm = FetcherSession(
            proxy=proxy,
            stealthy_headers=True,
            impersonate="chrome",
            timeout=_REQUEST_TIMEOUT_S,
        )
        self.session = await self._cm.__aenter__()

    async def close(self) -> None:
        if self._cm is not None:
            with suppress(Exception):
                await self._cm.__aexit__(None, None, None)
        self._cm = self.session = None

    async def rotate(self) -> Any | None:
        """Drop the current IP and connect through a fresh one."""
        await self.close()
        self.rotations += 1
        await self._open()
        logger.info("[tiktok] rotated proxy session (rotation #%d)", self.rotations)
        return self.session

    async def pace(self) -> None:
        """Sleep to hold this sticky IP under TikTok's per-IP rate threshold."""
        wait = _MIN_INTERVAL_S - (time.monotonic() - self._last_at)
        if wait > 0:
            await asyncio.sleep(wait + random.uniform(0, _PACE_JITTER_S))
        self._last_at = time.monotonic()


async def open_proxy_holder() -> _RotatingSession:
    """Open a warm rotate-on-block session holder (caller owns ``close()``)."""
    holder = _RotatingSession()
    await holder._open()
    return holder


@asynccontextmanager
async def bind_proxy_holder(holder: _RotatingSession):
    """Route this task's fetches through ``holder`` for the enclosed block."""
    token = _current_session.set(holder)
    try:
        yield holder
    finally:
        _current_session.reset(token)


@asynccontextmanager
async def proxy_session():
    """Open one reused, rotate-on-block proxy session for a continuation chain."""
    holder = await open_proxy_holder()
    try:
        async with bind_proxy_holder(holder):
            yield holder
    finally:
        await holder.close()
