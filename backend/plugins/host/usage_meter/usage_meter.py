"""The host's usage meter: calls counted in memory and written to the store every minute."""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import datetime

import anyio

from host.usage_meter.call_counts import CallCounts, CallKey
from host.usage_meter.logged_once import LoggedOnce
from host.usage_meter.meter_settings import MeterSettings
from host.usage_meter.rollup import PostHogRollup
from host.usage_meter.usage_store import DailyUsage, UsageStore
from host.usage_meter.utc_days import day_before, day_of, months_before, utc_now

logger = logging.getLogger(__name__)

FLUSH_SECONDS = 60.0
# The day's jobs are idempotent: hourly retries a failed send and catches up after a restart.
DAILY_JOBS_SECONDS = 3600.0
# Per-license rows are kept this long, as the privacy policy says.
KEPT_MONTHS = 13
# The last write at shutdown waits no longer than this.
CLOSE_SECONDS = 10.0


class UsageMeter:
    """Best effort: what it does may never fail, block or slow a call."""

    def __init__(
        self,
        store: UsageStore,
        rollup: PostHogRollup | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._store = store
        self._rollup = rollup
        self._clock = clock
        self._counts = CallCounts()
        # Held while counts are written, so a reader's flush waits for a write under way.
        self._writing = anyio.Lock()
        self.failures = LoggedOnce(logger)

    @classmethod
    def from_settings(
        cls, settings: MeterSettings, clock: Callable[[], datetime] = utc_now
    ) -> "UsageMeter":
        rollup = (
            PostHogRollup(settings.posthog_api_key, settings.posthog_host)
            if settings.posthog_api_key
            else None
        )
        return cls(UsageStore(settings.db_path), rollup, clock)

    def today(self) -> str:
        return day_of(self._clock())

    def record(self, key: CallKey, ms: int) -> None:
        self._counts.add(key, ms)

    async def flush(self) -> None:
        """Write the counts so far; a failed write keeps them for the next one."""
        async with self._writing:
            taken = self._counts.take()
            if not taken:
                return
            try:
                await anyio.to_thread.run_sync(self._store.add, taken)
            except Exception:
                self._counts.put_back(taken)
                self.failures.failed("writing the counts")

    async def daily_usage(self, day: str) -> DailyUsage:
        await self.flush()
        return await anyio.to_thread.run_sync(self._store.daily_usage, day)

    async def first_seen(self) -> dict[str, str]:
        """Each license id's first day with a call."""
        await self.flush()
        return await anyio.to_thread.run_sync(self._store.first_seen)

    async def run_daily_jobs(self) -> None:
        """Forget rows older than KEPT_MONTHS, and send yesterday's rollup once."""
        today = self.today()
        await self.flush()
        try:
            cutoff = months_before(today, KEPT_MONTHS)
            await anyio.to_thread.run_sync(self._store.forget_before, cutoff)
        except Exception:
            self.failures.failed("forgetting old rows")
        if self._rollup is None:
            return
        yesterday = day_before(today)
        try:
            if await anyio.to_thread.run_sync(self._store.rollup_sent, yesterday):
                return
            usage = await anyio.to_thread.run_sync(self._store.daily_usage, yesterday)
            await self._rollup.send(usage)
            await anyio.to_thread.run_sync(self._store.mark_rollup_sent, yesterday)
        except Exception:
            self.failures.failed("sending the daily rollup")

    @asynccontextmanager
    async def running(self) -> AsyncIterator[None]:
        """While the host serves: writes every minute, the day's jobs at once and hourly.

        The counts are written once more at shutdown, after the last call has ended.
        """
        try:
            async with anyio.create_task_group() as jobs:
                jobs.start_soon(self._every, FLUSH_SECONDS, self.flush, False)
                jobs.start_soon(
                    self._every, DAILY_JOBS_SECONDS, self.run_daily_jobs, True
                )
                try:
                    yield
                finally:
                    jobs.cancel_scope.cancel()
        finally:
            with anyio.move_on_after(CLOSE_SECONDS, shield=True):
                await self.flush()

    async def _every(
        self, seconds: float, job: Callable[[], Awaitable[None]], at_once: bool
    ) -> None:
        if not at_once:
            await anyio.sleep(seconds)
        while True:
            try:
                await job()
            except Exception:
                self.failures.failed("a scheduled job")
            await anyio.sleep(seconds)
