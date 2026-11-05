"""Runs the app's own job-pack check at startup, then once a day, for as long as the API runs,
and checks a code once more after the run that held it back ends.

While a run holds a code back, the schedule looks every FOLLOW_UP_EVERY, reading only the
runs, and checks the codes whose runs have ended; with none held back it sleeps until the
next day's check, and a code held back meanwhile wakes it. Nothing runs more often.

It stops within its bound however a check is caught: the loop ends on its flag, every await
is cancellable, and every database stretch is a session of its own on a worker thread, so a
cancel never closes a session under a thread.
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager, suppress
from datetime import timedelta

from sqlalchemy.orm import Session, sessionmaker

from modules.jobs.packs.delivery.automatic_delivery import (
    deliver_held_back,
    deliver_if_due,
)
from modules.jobs.packs.delivery.held_back import HELD_BACK

# Whatever the outcome: a failed check waits for the next day, never retried at once.
CHECK_EVERY = timedelta(days=1)
# How often a code a run held back is looked at while one is: a run's end is seen within it.
FOLLOW_UP_EVERY = timedelta(seconds=60)
# How long stopping waits for a check under way before cancelling it. Its session work
# takes milliseconds; only its download can take longer.
STOP_WITHIN = timedelta(seconds=2)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def delivering_daily(
    session_factory: sessionmaker[Session],
) -> AsyncIterator[None]:
    stopping = asyncio.Event()
    # Set when a code is held back, or when stopping: either way the loop wakes.
    nudged = asyncio.Event()
    loop = asyncio.get_running_loop()
    unlisten = HELD_BACK.listen(lambda: _nudge(loop, nudged))
    task = asyncio.create_task(
        _daily(session_factory, stopping, nudged), name="job-pack-delivery"
    )
    try:
        yield
    finally:
        unlisten()
        stopping.set()
        nudged.set()
        with suppress(TimeoutError):
            await asyncio.wait_for(asyncio.shield(task), STOP_WITHIN.total_seconds())
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


def _nudge(loop: asyncio.AbstractEventLoop, nudged: asyncio.Event) -> None:
    """From whatever thread held a code back; a loop already closed has nothing to wake."""
    with suppress(RuntimeError):
        loop.call_soon_threadsafe(nudged.set)


async def _daily(
    session_factory: sessionmaker[Session],
    stopping: asyncio.Event,
    nudged: asyncio.Event,
) -> None:
    # The loop ends on `stopping`, not on the cancel alone: a cancel that lands mid-check can
    # surface as another error, which the check's handler catches.
    loop = asyncio.get_running_loop()
    check_at = loop.time()
    look_at: float | None = None
    while True:
        # Cleared before anything is read, so a code held back from here on wakes the wait.
        nudged.clear()
        if stopping.is_set():
            return
        if loop.time() >= check_at:
            await _caught(
                deliver_if_due(session_factory),
                "could not check for the license's job packs",
            )
            check_at = loop.time() + CHECK_EVERY.total_seconds()
            # Every code was just checked: one held back now waits a whole period.
            look_at = None
        elif look_at is not None and loop.time() >= look_at:
            await _caught(
                deliver_held_back(session_factory),
                "could not check again the job packs a run held back",
            )
            look_at = None
        if not HELD_BACK.held():
            look_at = None
        elif look_at is None:
            look_at = loop.time() + FOLLOW_UP_EVERY.total_seconds()
        wake_at = check_at if look_at is None else min(check_at, look_at)
        with suppress(TimeoutError):
            await asyncio.wait_for(nudged.wait(), max(0.0, wake_at - loop.time()))


async def _caught(check: Awaitable[None], failure: str) -> None:
    try:
        await check
    except Exception:
        logger.exception(failure)
