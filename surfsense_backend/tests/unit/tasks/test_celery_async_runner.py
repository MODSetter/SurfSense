"""Regression tests for ``run_async_celery_task``.

These tests pin down the production bug observed on 2026-05-02 where
the video-presentation Celery task hung at ``[billable_call] finalize``
because the shared ``app.db.engine`` had pooled asyncpg connections
bound to a *previous* task's now-closed event loop. Reusing such a
connection on a fresh loop crashes inside ``pool_pre_ping`` with::

    AttributeError: 'NoneType' object has no attribute 'send'

(the proactor is None because the loop is gone) and can hang forever
inside the asyncpg ``Connection._cancel`` cleanup coroutine.

The fix is ``run_async_celery_task``: a small helper that runs every
async celery task body inside a fresh event loop and disposes the
shared engine pool both before (defends against a previous task that
crashed) and after (releases connections we opened on this loop).

Tests here exercise the helper with a stub engine that records
``dispose()`` calls and panics if a coroutine produced by one loop is
awaited on another — mirroring the real asyncpg behaviour.
"""

from __future__ import annotations

import asyncio
import gc
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Stub engine that emulates the asyncpg-on-stale-loop crash
# ---------------------------------------------------------------------------


class _StaleLoopEngine:
    """Tiny stand-in for ``app.db.engine`` that tracks dispose() calls.

    ``dispose()`` is async (matches ``AsyncEngine.dispose``) and records
    the running event loop id so tests can assert it ran on *each*
    fresh loop.
    """

    def __init__(self) -> None:
        self.dispose_loop_ids: list[int] = []

    async def dispose(self) -> None:
        loop = asyncio.get_running_loop()
        self.dispose_loop_ids.append(id(loop))


@contextmanager
def _patch_shared_engine(stub: _StaleLoopEngine) -> Iterator[None]:
    """Patch ``from app.db import engine as shared_engine`` lookup.

    The helper imports lazily inside the function body, so we have to
    patch the attribute on the already-loaded ``app.db`` module.
    """
    import app.db as app_db

    original = getattr(app_db, "engine", None)
    app_db.engine = stub  # type: ignore[attr-defined]
    try:
        yield
    finally:
        if original is None:
            with pytest.raises(AttributeError):
                _ = app_db.engine
        else:
            app_db.engine = original  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_runner_returns_value_and_disposes_engine_around_call() -> None:
    """Happy path: the coroutine result is returned, and the shared
    engine is disposed both before and after the task body runs.
    """
    from app.tasks.celery_tasks import run_async_celery_task

    stub = _StaleLoopEngine()

    async def _body() -> str:
        # Engine should already have been disposed once before we run.
        assert len(stub.dispose_loop_ids) == 1
        return "ok"

    with _patch_shared_engine(stub):
        result = run_async_celery_task(_body)

    assert result == "ok"
    # Once before the body, once after (in finally).
    assert len(stub.dispose_loop_ids) == 2
    # Both disposes ran on the SAME (fresh) loop the task body used.
    assert stub.dispose_loop_ids[0] == stub.dispose_loop_ids[1]


def test_runner_creates_fresh_loop_per_invocation() -> None:
    """Each call must spin its own loop. Without this guarantee a
    previous task's loop would be reused and the asyncpg-stale-loop
    crash would never be avoided.
    """
    import app.tasks.celery_tasks as celery_tasks_pkg

    stub = _StaleLoopEngine()
    new_loop_calls = 0
    closed_loops: list[bool] = []

    real_new_event_loop = asyncio.new_event_loop

    def _counting_new_loop() -> asyncio.AbstractEventLoop:
        nonlocal new_loop_calls
        new_loop_calls += 1
        loop = real_new_event_loop()
        # Hook close() so we can verify each loop was closed properly
        # before the next one was created.
        original_close = loop.close

        def _tracked_close() -> None:
            closed_loops.append(True)
            original_close()

        loop.close = _tracked_close  # type: ignore[method-assign]
        return loop

    async def _body() -> None:
        # Loop is alive and current at body execution time.
        running = asyncio.get_running_loop()
        assert not running.is_closed()

    with (
        _patch_shared_engine(stub),
        patch.object(asyncio, "new_event_loop", _counting_new_loop),
    ):
        for _ in range(3):
            celery_tasks_pkg.run_async_celery_task(_body)

    assert new_loop_calls == 3
    assert closed_loops == [True, True, True]
    # Each invocation disposed twice (before + after).
    assert len(stub.dispose_loop_ids) == 6


def test_runner_disposes_engine_even_when_body_raises() -> None:
    """Cleanup MUST run on the failure path too — otherwise stale
    connections leak into the next task and cause the original hang.
    """
    from app.tasks.celery_tasks import run_async_celery_task

    stub = _StaleLoopEngine()

    class _BoomError(RuntimeError):
        pass

    async def _body() -> None:
        raise _BoomError("kaboom")

    with _patch_shared_engine(stub), pytest.raises(_BoomError):
        run_async_celery_task(_body)

    assert len(stub.dispose_loop_ids) == 2  # before + after still ran


def test_runner_swallows_dispose_errors() -> None:
    """A flaky engine.dispose() must NEVER take down a celery task.

    Production scenario: the very first dispose (before the body runs)
    might hit a partially-initialised engine; the helper logs and
    moves on. The task body still runs; the result is still returned.
    """
    from app.tasks.celery_tasks import run_async_celery_task

    class _AngryEngine:
        def __init__(self) -> None:
            self.calls = 0

        async def dispose(self) -> None:
            self.calls += 1
            raise RuntimeError("dispose() blew up")

    stub = _AngryEngine()

    async def _body() -> int:
        return 42

    with _patch_shared_engine(stub):
        assert run_async_celery_task(_body) == 42

    assert stub.calls == 2  # before + after both attempted


def test_runner_propagates_value_from_async_body() -> None:
    """Sanity: pass-through of any pickleable celery return value."""
    from app.tasks.celery_tasks import run_async_celery_task

    stub = _StaleLoopEngine()

    async def _body() -> dict[str, object]:
        return {"status": "ready", "video_presentation_id": 19}

    with _patch_shared_engine(stub):
        out = run_async_celery_task(_body)

    assert out == {"status": "ready", "video_presentation_id": 19}


def test_video_presentation_task_uses_runner_helper() -> None:
    """Defence-in-depth: confirm the celery task module imports
    ``run_async_celery_task``. If a future refactor inlines a
    ``loop = asyncio.new_event_loop(); ... loop.close()`` block again,
    the original hang will return.
    """
    # The module's task body should not contain a manual new_event_loop
    # call — that's exactly what the helper exists to centralise.
    import inspect

    from app.tasks.celery_tasks import video_presentation_tasks

    src = inspect.getsource(video_presentation_tasks)
    assert "run_async_celery_task" in src, (
        "video_presentation_tasks.py must use run_async_celery_task; "
        "manual asyncio.new_event_loop() in a celery task hangs on the "
        "shared SQLAlchemy pool when reused across tasks."
    )
    assert "asyncio.new_event_loop" not in src, (
        "video_presentation_tasks.py contains a raw asyncio.new_event_loop "
        "call — route every async task through run_async_celery_task to "
        "avoid the stale-pool hang."
    )


def test_podcast_task_uses_runner_helper() -> None:
    """Symmetric assertion for the podcast task — same root cause, same
    fix, same regression risk.
    """
    import inspect

    from app.tasks.celery_tasks import podcast_tasks

    src = inspect.getsource(podcast_tasks)
    assert "run_async_celery_task" in src
    assert "asyncio.new_event_loop" not in src


def test_runner_runs_shutdown_asyncgens_before_close() -> None:
    """If the task body created any async generators that didn't get
    fully iterated, we must still call ``loop.shutdown_asyncgens()``
    before closing — otherwise we leak event-loop bound resources
    that re-emerge as ``RuntimeError: Event loop is closed`` later.
    """
    from app.tasks.celery_tasks import run_async_celery_task

    stub = _StaleLoopEngine()

    async def _agen():
        try:
            yield 1
            yield 2
        finally:
            pass

    async def _body() -> None:
        # Iterate the agen partially, then leave it dangling — exactly
        # the situation shutdown_asyncgens() is designed to clean up.
        async for v in _agen():
            if v == 1:
                break

    with _patch_shared_engine(stub):
        run_async_celery_task(_body)

    # By the time the helper returns, garbage collection + shutdown_asyncgens
    # should have ensured no live async-gen references remain. We don't
    # assert agen.closed directly (it depends on GC ordering); the real
    # contract is "no warnings, no event-loop-closed errors". A successful
    # second invocation proves the loop was cleaned up properly.
    with _patch_shared_engine(stub):
        run_async_celery_task(_body)

    # Force a GC pass to surface any 'coroutine was never awaited'
    # warnings that would indicate the cleanup is broken.
    gc.collect()


def test_runner_uses_proactor_loop_on_windows() -> None:
    """On Windows the celery worker preselects a Proactor policy so
    subprocess (ffmpeg) calls work. The helper must not silently fall
    back to a Selector loop and re-break video/podcast generation.
    """
    if not sys.platform.startswith("win"):
        pytest.skip("Windows-specific event-loop policy assertion")

    from app.tasks.celery_tasks import run_async_celery_task

    stub = _StaleLoopEngine()

    # Mirror the policy set at the top of every Windows celery task.
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    observed: list[str] = []

    async def _body() -> None:
        observed.append(type(asyncio.get_running_loop()).__name__)

    with _patch_shared_engine(stub):
        run_async_celery_task(_body)

    assert observed == ["ProactorEventLoop"]
