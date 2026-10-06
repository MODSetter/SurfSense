import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable

from modules.chat.runs.run import Run, RunState

logger = logging.getLogger(__name__)

# How long a stop waits for the reply to store what it has, so the caller's
# next read sees the stopped turn.
STOP_SETTLE_SECONDS = 5.0


class RunActiveError(Exception):
    """The thread is already answering; a second reply would interleave with it."""


class ChatRuns:
    """The replies being generated, at most one per thread.

    In memory: the API dies with the app, so nothing stored would outlive a
    run anyway, and one uvicorn process serves every window.
    """

    def __init__(self) -> None:
        self._runs: dict[int, Run] = {}

    def get(self, thread_id: int) -> Run | None:
        return self._runs.get(thread_id)

    def running(self) -> frozenset[int]:
        return frozenset(self._runs)

    async def stop(self, thread_id: int, timeout: float) -> None:
        """Stop the thread's run and wait, at most `timeout` seconds, for it to
        store what it has; nothing to do when the thread is not answering."""
        run = self._runs.get(thread_id)
        if run is None or run.task is None:
            return
        task = run.task
        run.stop()
        await asyncio.wait({task}, timeout=timeout)

    async def interrupt_all(self, timeout: float) -> None:
        """End every run and wait, at most `timeout` seconds, for each to store
        what it has. Bounded: a quit never waits on a reply that cannot."""
        tasks = {run.task for run in self._runs.values() if run.task is not None}
        for run in tuple(self._runs.values()):
            run.interrupt()
        if tasks:
            await asyncio.wait(tasks, timeout=timeout)

    def start(
        self,
        thread_id: int,
        frames: Callable[[Run], AsyncIterator[bytes]],
        on_end: Callable[[], Awaitable[None]],
        on_state: Callable[[RunState], None] | None = None,
    ) -> Run:
        """Begin a reply in the background; it keeps going whoever watches."""
        if thread_id in self._runs:
            raise RunActiveError("this thread is still answering")
        run = Run(on_state)
        self._runs[thread_id] = run
        run.task = asyncio.create_task(self._drive(thread_id, run, frames, on_end))
        return run

    async def _drive(
        self,
        thread_id: int,
        run: Run,
        frames: Callable[[Run], AsyncIterator[bytes]],
        on_end: Callable[[], Awaitable[None]],
    ) -> None:
        try:
            async for frame in frames(run):
                run.add(frame)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("chat run for thread %s failed", thread_id)
        finally:
            # The reply is stored before the frames end, so a follower that
            # finds no run reads the finished turn instead. Gone from the
            # registry before `on_end` announces it, so a window that reloads
            # on that notice no longer sees the thread running.
            del self._runs[thread_id]
            run.finish()
            await asyncio.shield(on_end())
