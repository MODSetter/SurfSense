"""Runs the app's own renewal check at startup, then once a day, for as long as the API runs."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from datetime import timedelta

from sqlalchemy.orm import Session, sessionmaker

from modules.license.renewal.automatic_renewal import renew_if_due

# Whatever the outcome: a failed check waits for the next day, never retried at once.
CHECK_EVERY = timedelta(days=1)
# How long stopping waits for a check under way before cancelling it. Its session
# work takes milliseconds; only its call to the license server can take longer.
STOP_WITHIN = timedelta(seconds=2)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def renewing_daily(session_factory: sessionmaker[Session]) -> AsyncIterator[None]:
    stopping = asyncio.Event()
    task = asyncio.create_task(
        _daily(session_factory, stopping), name="license-renewal"
    )
    try:
        yield
    finally:
        stopping.set()
        # A check under way finishes first: cancelled inside a transaction, its
        # session would close while a worker thread still uses it.
        with suppress(TimeoutError):
            await asyncio.wait_for(asyncio.shield(task), STOP_WITHIN.total_seconds())
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


async def _daily(
    session_factory: sessionmaker[Session], stopping: asyncio.Event
) -> None:
    # The loop ends on `stopping`, not on the cancel alone: a cancel that lands in a
    # transaction can surface as another error, which the check's handler catches.
    while not stopping.is_set():
        try:
            await renew_if_due(session_factory)
        except Exception:
            logger.exception("could not check for a renewed license file")
        with suppress(TimeoutError):
            await asyncio.wait_for(stopping.wait(), CHECK_EVERY.total_seconds())
