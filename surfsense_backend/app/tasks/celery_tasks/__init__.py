"""Celery tasks package.

Also hosts the small helpers every async celery task should use to
spin up its event loop. See :func:`run_async_celery_task` for the
canonical pattern.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import config

logger = logging.getLogger(__name__)

_celery_engine = None
_celery_session_maker = None


def get_celery_session_maker() -> async_sessionmaker:
    """Return a shared async session maker for Celery tasks.

    A single NullPool engine is created per worker process and reused
    across all task invocations to avoid leaking engine objects.
    """
    global _celery_engine, _celery_session_maker
    if _celery_session_maker is None:
        _celery_engine = create_async_engine(
            config.DATABASE_URL,
            poolclass=NullPool,
            echo=False,
        )
        _celery_session_maker = async_sessionmaker(
            _celery_engine, expire_on_commit=False
        )
    return _celery_session_maker


def _dispose_shared_db_engine(loop: asyncio.AbstractEventLoop) -> None:
    """Drop the shared ``app.db.engine`` connection pool synchronously.

    The shared engine (used by ``shielded_async_session`` and most
    routes / services) is a module-level singleton with a real pool.
    Each celery task creates a fresh ``asyncio`` event loop; asyncpg
    connections cache a reference to whichever loop opened them. When
    a subsequent task's loop pulls a stale connection from the pool,
    SQLAlchemy's ``pool_pre_ping`` checkout crashes with::

        AttributeError: 'NoneType' object has no attribute 'send'
        File ".../asyncio/proactor_events.py", line 402, in _loop_writing
            self._write_fut = self._loop._proactor.send(self._sock, data)

    or hangs forever inside the asyncpg ``Connection._cancel`` cleanup
    coroutine that can never run because its loop is gone.

    Disposing the engine forces the pool to drop every cached
    connection so the next checkout opens a fresh one on the current
    loop. Safe to call from a task's finally block; failure is logged
    but never propagated.
    """
    try:
        from app.db import engine as shared_engine

        loop.run_until_complete(shared_engine.dispose())
    except Exception:
        logger.warning("Shared DB engine dispose() failed", exc_info=True)


T = TypeVar("T")


def run_async_celery_task[T](coro_factory: Callable[[], Awaitable[T]]) -> T:
    """Run an async coroutine inside a fresh event loop with proper
    DB-engine cleanup.

    This is the canonical entry point for every async celery task.
    It performs three responsibilities that were previously copy-pasted
    (incorrectly) across each task module:

    1. Create a fresh ``asyncio`` loop and install it on the current
       thread (celery's ``--pool=solo`` runs every task on the main
       thread, but other pool types don't).
    2. Dispose the shared ``app.db.engine`` BEFORE the task runs so
       any stale connections left over from a previous task's loop
       are dropped — defends against tasks that crashed without
       cleaning up.
    3. Dispose the shared engine AFTER the task runs so the
       connections we opened on this loop are released before the
       loop closes (avoids ``coroutine 'Connection._cancel' was
       never awaited`` warnings and the next-task hang).

    Use as::

        @celery_app.task(name="my_task", bind=True)
        def my_task(self, *args):
            return run_async_celery_task(lambda: _my_task_impl(*args))
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # Defense-in-depth: prior task may have crashed before
        # disposing. Idempotent — no-op if pool is already empty.
        _dispose_shared_db_engine(loop)
        return loop.run_until_complete(coro_factory())
    finally:
        # Drop any connections this task opened so they don't leak
        # into the next task's loop.
        _dispose_shared_db_engine(loop)
        with contextlib.suppress(Exception):
            loop.run_until_complete(loop.shutdown_asyncgens())
        with contextlib.suppress(Exception):
            asyncio.set_event_loop(None)
        loop.close()


__all__ = [
    "get_celery_session_maker",
    "run_async_celery_task",
]
