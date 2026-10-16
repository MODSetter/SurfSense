"""What the scraper plugins keep warm across calls, closed once when the host stops.

A plugin's `server.py` may expose a `lifespan` that the host enters at startup. The
shared pools (kept HTTP sessions, browsers, API clients) register their close here,
and the last plugin to leave closes them all, once.
"""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import anyio

logger = logging.getLogger(__name__)

# How long the pools may take to close, a browser's included: they close at once.
CLOSE_SECONDS = 15.0

_closers: list[Callable[[], Awaitable[None]]] = []
_entered = 0


def at_shutdown(close: Callable[[], Awaitable[None]]) -> None:
    """Run `close` when the host stops; registering the same one twice runs it once."""
    if close not in _closers:
        _closers.append(close)


@asynccontextmanager
async def lifespan() -> AsyncIterator[None]:
    """Entered by each plugin's lifespan; the last to leave closes every pool."""
    global _entered
    _entered += 1
    try:
        yield
    finally:
        _entered -= 1
        if _entered == 0:
            # Shielded: the host cuts a slow plugin's exit short, and the pools
            # must close all the same.
            with anyio.CancelScope(shield=True):
                await close_all()


async def close_all() -> None:
    """Close every registered pool at once, all within `CLOSE_SECONDS`.

    The pools are independent, and one at a time a few slow ones would outlast the
    container's stop grace. One failing or hanging skips none of the others.
    """
    closing = _closers[::-1]
    _closers.clear()
    async with anyio.create_task_group() as group:
        for close in closing:
            group.start_soon(_closed, close)


async def _closed(close: Callable[[], Awaitable[None]]) -> None:
    try:
        with anyio.fail_after(CLOSE_SECONDS):
            await close()
    except Exception:
        logger.exception("[scraping] closing a shared pool failed")
