"""Rotate-on-block proxy sessions for TikTok, on the shared keep-alive holders.

A holder keeps one connection open, so one residential exit IP serves the warm-up
and every later fetch, and the ``ttwid`` cookie (bound to that IP) stays valid.
Each rotation walks to the next country pool: TikTok withholds ``ttwid`` from the
provider's worldwide pool but mints it on country-pinned exits (see
:func:`proprietary.scraping.proxy.rotation.country_for_rotation`). The TikTok
specifics on top of :mod:`proprietary.scraping.sessions` are that walk, a per-IP
pace and the progress hook.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any
from weakref import WeakKeyDictionary

from proprietary.scraping import sessions
from proprietary.scraping.proxy.rotation import country_for_rotation

PLUGIN = "tiktok"

# Pace each sticky IP so a fast exit can't burst past TikTok's per-IP threshold.
_MIN_INTERVAL_S = 0.5
_PACE_JITTER_S = 0.25
# A healthy fetch lands in ~1-2 s; a dead exit fails at connect (5 s) or the whole
# request at 15 s, the old single bound, then the caller rotates.
REQUEST_TIMEOUT = (5.0, 10.0)

# When each holder last sent, for the pace.
_last_at: WeakKeyDictionary[Any, float] = WeakKeyDictionary()

on_stage: ContextVar[Callable[[str], Awaitable[None]] | None] = ContextVar(
    "tiktok_on_stage", default=None
)
"""The tool's progress hook: hears each stage (attempt started, page fetched)."""


async def report_stage(message: str) -> None:
    report = on_stage.get()
    if report is not None:
        await report(message)


def first_exit() -> sessions.Exit:
    """The rotating gateway in the first rotation country."""
    return sessions.Exit(country_for_rotation(0))


async def rotate(h: sessions.SessionHolder, reason: str, *, seen: int) -> None:
    """Move ``h`` to the next country pool (a no-op if it rotated since ``seen``)."""
    await h.rotate(reason, country=country_for_rotation(seen + 1), seen=seen)


async def pace(h: Any) -> None:
    """Sleep to hold this holder's IP under TikTok's per-IP rate threshold."""
    wait = _MIN_INTERVAL_S - (time.monotonic() - _last_at.get(h, 0.0))
    if wait > 0:
        await asyncio.sleep(wait + random.uniform(0, _PACE_JITTER_S))
    _last_at[h] = time.monotonic()


@asynccontextmanager
async def proxy_session() -> AsyncIterator[sessions.SessionHolder]:
    """One rotate-on-block holder for a continuation chain, bound for the block."""
    async with sessions.bound(PLUGIN, first_exit()) as h:
        yield h
