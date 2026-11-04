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

logger = logging.getLogger(__name__)


@asynccontextmanager
async def renewing_daily(session_factory: sessionmaker[Session]) -> AsyncIterator[None]:
    task = asyncio.create_task(_daily(session_factory), name="license-renewal")
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


async def _daily(session_factory: sessionmaker[Session]) -> None:
    while True:
        try:
            await renew_if_due(session_factory)
        except Exception:
            logger.exception("could not check for a renewed license file")
        await asyncio.sleep(CHECK_EVERY.total_seconds())
