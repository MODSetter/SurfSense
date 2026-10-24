"""Bounded fan-out that keeps input order, and first-wins hedging of slow attempts.

Most plugins run their sources, pages or chains one after another, so a call takes
the sum of its parts, and one slow exit sets the tail (walmart, 3 URLs: 7.44 s =
2.48 + 2.79 + 2.15). :func:`ordered_map` runs them side by side and still yields in
input order, which the item limits and the MCP progress counts rely on.
:func:`hedged` starts a second attempt on a fresh exit when the first is slow, and
keeps whichever is accepted first.
"""

from __future__ import annotations

import asyncio
import contextvars
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from contextlib import AbstractAsyncContextManager, nullcontext
from typing import Any

from proprietary.scraping import sessions
from proprietary.scraping.config import Config
from proprietary.scraping.http import HEDGE_INDEX

logger = logging.getLogger(__name__)

_MISSING: Any = object()


async def ordered_map[T, R](
    items: Iterable[T],
    fn: Callable[[T], Awaitable[R]],
    *,
    concurrency: int,
    worker_context: Callable[[], AbstractAsyncContextManager[Any]] | None = None,
    max_ahead: int | None = None,
) -> AsyncIterator[R]:
    """Run ``fn`` over ``items``, at most ``concurrency`` at once, yielding in order.

    A result is yielded as soon as it and every result before it are done. If
    ``fn`` raises, the results before it are yielded, then the error is raised and
    nothing after it is started. Each worker task enters ``worker_context()`` once
    and runs its jobs inside it, so a holder bound there is ``current()`` in ``fn``.

    No job starts ``max_ahead`` (default ``2 * concurrency``) or more items past
    the oldest result not yet yielded: behind a slow head, or ahead of a consumer
    that stops at a limit, the rest of the list is not sent and buffered meanwhile.

    When the consumer stops (break, ``aclose``, an error, cancellation) every
    pending job is cancelled and awaited. Wrap the call in
    ``contextlib.aclosing`` so that happens before the consumer moves on; a bare
    ``break`` leaves it to the garbage collector's ``aclose``.
    """
    ahead = max(1, 2 * concurrency if max_ahead is None else max_ahead)
    source = iter(items)
    results: dict[int, tuple[bool, Any]] = {}
    changed = asyncio.Event()  # a result landed or a worker ended: for the consumer
    advanced = asyncio.Event()  # the head moved: for workers waiting for room
    next_index = 0
    head = 0  # the next index to yield
    stop_at: int | None = None  # the first failed index; nothing after it starts
    crash: BaseException | None = None

    async def take() -> tuple[int, T] | None:
        nonlocal next_index, stop_at
        while next_index - head >= ahead and (stop_at is None or next_index <= stop_at):
            advanced.clear()
            await advanced.wait()
        if stop_at is not None and next_index > stop_at:
            return None
        index = next_index
        try:
            item = next(source)
        except StopIteration:
            stop_at = index if stop_at is None else min(stop_at, index)
            return None
        next_index += 1
        return index, item

    async def worker() -> None:
        nonlocal stop_at, crash
        try:
            job = await take()  # a worker with nothing to do never opens its context
            if job is None:
                return
            async with worker_context() if worker_context else nullcontext():
                while job is not None:
                    index, item = job
                    try:
                        results[index] = (True, await fn(item))
                    except Exception as e:
                        results[index] = (False, e)
                        stop_at = index if stop_at is None else min(stop_at, index)
                    except asyncio.CancelledError as e:
                        task = asyncio.current_task()
                        if task is None or task.cancelling():
                            raise
                        # fn let a CancelledError out while nobody cancelled this
                        # worker: a failure of this item, not the end of the map.
                        error = RuntimeError(f"ordered_map: item {index} was cancelled")
                        error.__cause__ = e
                        results[index] = (False, error)
                        stop_at = index if stop_at is None else min(stop_at, index)
                    changed.set()
                    job = await take()
        except Exception as e:  # the worker context or the items iterator failed
            crash = crash or e
        finally:
            changed.set()

    workers = [asyncio.create_task(worker()) for _ in range(max(1, concurrency))]
    try:
        while True:
            if head in results:
                ok, value = results.pop(head)
                if not ok:
                    raise value
                head += 1
                advanced.set()
                yield value
                continue
            if crash is not None:
                raise crash
            if stop_at is not None and head >= stop_at:
                return  # the source ran out at stop_at
            if all(w.done() for w in workers):
                # Never end short in silence: a worker died without its result.
                raise RuntimeError(f"ordered_map: item {head} ended without a result")
            changed.clear()
            await changed.wait()
    finally:
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)


async def hedged[R](
    attempt: Callable[[int], Awaitable[R]],
    *,
    after_s: float,
    accept: Callable[[R], bool] = lambda r: True,
    max_extra: int = 1,
    plugin: str = "scraping",
    stage: str = "hedge",
) -> R:
    """``attempt(0)``, plus ``attempt(1..max_extra)`` each ``after_s`` it stays slow.

    By contract ``attempt(i)`` with ``i > 0`` uses a fresh exit (its own holder);
    it runs with no holder bound, so fetch helpers that look one up through
    ``sessions.current()`` fall back to a one-off request on a fresh exit.
    The first result ``accept`` passes wins; the other attempts are cancelled and
    awaited, so their ``holder`` blocks close their sessions before this returns.
    A hedge starts only while an earlier attempt is still running: an attempt that
    fails fast is not retried here, the plugin's rotation loop does that. With no
    accepted result, returns the first rejected result, else raises the first
    attempt's error. ``SCRAPING_HEDGE=0`` runs ``attempt(0)`` alone.
    """
    extra = max(0, max_extra) if Config.HEDGE else 0
    started = time.monotonic()
    tasks: list[asyncio.Task[R]] = []

    def launch() -> asyncio.Task[R]:
        ctx = contextvars.copy_context()
        ctx.run(HEDGE_INDEX.set, len(tasks))
        if tasks:  # a hedge on the slow attempt's own exit would be no hedge at all
            ctx.run(sessions._current.set, None)
        task = asyncio.create_task(_call(attempt, len(tasks)), context=ctx)
        tasks.append(task)
        return task

    pending = {launch()}
    rejected: Any = _MISSING
    errors: dict[int, BaseException] = {}
    winner = -1
    try:
        while pending:
            wait_s = None
            if len(tasks) <= extra:
                wait_s = max(0.0, started + after_s * len(tasks) - time.monotonic())
            done, pending = await asyncio.wait(
                pending, timeout=wait_s, return_when=asyncio.FIRST_COMPLETED
            )
            if not done:
                pending.add(launch())
                continue
            for task in sorted(done, key=tasks.index):
                index = tasks.index(task)
                error = (
                    asyncio.CancelledError() if task.cancelled() else task.exception()
                )
                if error is not None:
                    errors[index] = error
                    continue
                result = task.result()
                if accept(result):
                    winner = index
                    return result
                if rejected is _MISSING:
                    rejected = result
        if rejected is not _MISSING:
            return rejected
        raise errors[min(errors)]
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if len(tasks) > 1:
            logger.info(
                "[%s][perf] stage=%s hedge=%d winner=%d ms=%.0f",
                plugin,
                stage,
                len(tasks) - 1,
                winner,
                (time.monotonic() - started) * 1000,
            )


async def _call[R](attempt: Callable[[int], Awaitable[R]], index: int) -> R:
    return await attempt(index)
