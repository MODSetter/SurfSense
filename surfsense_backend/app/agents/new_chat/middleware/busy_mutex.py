"""
BusyMutexMiddleware — per-thread asyncio lock + cancel token.

LangChain has no built-in concept of "this thread is already running a
turn — refuse the second concurrent request". Without it, a user
double-clicking "send" or refreshing the page mid-stream can spawn two
turns racing on the same checkpoint, producing duplicated tool calls
and mangled state.

Ported from OpenCode's ``Stream.scoped(AbortController)`` pattern: a
single-process, in-memory lock + cooperative cancellation token keyed by
``thread_id``. For multi-worker deployments a distributed lock backend
(Redis or PostgreSQL advisory locks) is a phase-2 follow-up.

What this provides:
- A ``WeakValueDictionary[str, asyncio.Lock]`` keyed by ``thread_id``;
  acquiring the lock during ``before_agent`` blocks any concurrent
  prompt on the same thread until release.
- A per-thread ``asyncio.Event`` (``cancel_event``) that long-running
  tools can poll to abort cooperatively. The event is reset between
  turns. Tools should check ``runtime.context.cancel_event.is_set()``
  in tight inner loops.
- A typed :class:`~app.agents.new_chat.errors.BusyError` raised when a
  second turn arrives while the lock is held.

Note: SurfSense's ``stream_new_chat`` is the call site that should
acquire/release. Wiring this as middleware means the contract is
explicit and the lock manager is shared with subagents that compile
their own ``create_agent`` runnables.
"""

from __future__ import annotations

import asyncio
import logging
import weakref
from typing import Any

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ContextT,
    ResponseT,
)
from langgraph.config import get_config
from langgraph.runtime import Runtime

from app.agents.new_chat.errors import BusyError

logger = logging.getLogger(__name__)


class _ThreadLockManager:
    """Process-local registry of per-thread asyncio locks + cancel events."""

    def __init__(self) -> None:
        self._locks: weakref.WeakValueDictionary[str, asyncio.Lock] = (
            weakref.WeakValueDictionary()
        )
        self._cancel_events: dict[str, asyncio.Event] = {}

    def lock_for(self, thread_id: str) -> asyncio.Lock:
        lock = self._locks.get(thread_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[thread_id] = lock
        return lock

    def cancel_event(self, thread_id: str) -> asyncio.Event:
        event = self._cancel_events.get(thread_id)
        if event is None:
            event = asyncio.Event()
            self._cancel_events[thread_id] = event
        return event

    def request_cancel(self, thread_id: str) -> bool:
        event = self._cancel_events.get(thread_id)
        if event is None:
            return False
        event.set()
        return True

    def reset(self, thread_id: str) -> None:
        event = self._cancel_events.get(thread_id)
        if event is not None:
            event.clear()


# Module-level singleton — process-local but reused across all agent
# instances built in this process. Subagents created in nested
# ``create_agent`` calls also get this so locks are coherent.
manager = _ThreadLockManager()


def get_cancel_event(thread_id: str) -> asyncio.Event:
    """Public accessor used by long-running tools to poll cancellation."""
    return manager.cancel_event(thread_id)


def request_cancel(thread_id: str) -> bool:
    """Trip the cancel event for ``thread_id``. Returns True if found."""
    return manager.request_cancel(thread_id)


def reset_cancel(thread_id: str) -> None:
    """Reset the cancel event for ``thread_id`` (called between turns)."""
    manager.reset(thread_id)


class BusyMutexMiddleware(AgentMiddleware[AgentState[ResponseT], ContextT, ResponseT]):
    """Block concurrent prompts on the same thread.

    Acquires the thread's lock in ``abefore_agent`` and releases in
    ``aafter_agent``. If the lock is held, raises :class:`BusyError`
    so the caller can emit a ``surfsense.busy`` SSE event with the
    in-flight request id.

    Args:
        require_thread_id: When True, raise :class:`BusyError` if no
            ``thread_id`` can be resolved from the active
            ``RunnableConfig``. Default is False — we treat a missing
            thread_id as "this turn has nothing to lock against" and
            no-op the mutex. Set True only when you trust the call
            site to always provide ``configurable.thread_id`` (e.g.
            in production where ``stream_new_chat`` always does).
    """

    def __init__(self, *, require_thread_id: bool = False) -> None:
        super().__init__()
        self._require_thread_id = require_thread_id
        self.tools = []
        # Per-call locks owned by this middleware. We track them as
        # an instance attribute so ``aafter_agent`` knows which lock
        # to release.
        self._held_locks: dict[str, asyncio.Lock] = {}

    @staticmethod
    def _thread_id(runtime: Runtime[ContextT]) -> str | None:
        """Extract ``thread_id`` from the active LangGraph ``RunnableConfig``.

        ``langgraph.runtime.Runtime`` deliberately does NOT expose ``config``.
        The runnable config (where ``configurable.thread_id`` lives) must be
        fetched via :func:`langgraph.config.get_config` from inside a node /
        middleware. We fall back to ``getattr(runtime, "config", None)`` for
        unit tests / legacy runtimes that synthesize a config-bearing stub.
        """

        def _from_dict(cfg: Any) -> str | None:
            if not isinstance(cfg, dict):
                return None
            tid = (cfg.get("configurable") or {}).get("thread_id")
            return str(tid) if tid is not None else None

        # Preferred path: real LangGraph runtime context.
        try:
            tid = _from_dict(get_config())
        except Exception:
            tid = None
        if tid is not None:
            return tid

        # Fallback for tests and any runtime that surfaces a config dict
        # directly on the runtime instance.
        return _from_dict(getattr(runtime, "config", None))

    async def abefore_agent(  # type: ignore[override]
        self,
        state: AgentState[Any],
        runtime: Runtime[ContextT],
    ) -> dict[str, Any] | None:
        del state
        thread_id = self._thread_id(runtime)
        if thread_id is None:
            if self._require_thread_id:
                raise BusyError("no thread_id configured")
            logger.debug(
                "BusyMutexMiddleware: no thread_id resolved from RunnableConfig; "
                "skipping per-thread lock for this turn."
            )
            return None

        lock = manager.lock_for(thread_id)
        if lock.locked():
            raise BusyError(request_id=thread_id)
        await lock.acquire()
        self._held_locks[thread_id] = lock
        # Reset the cancel event so this turn starts fresh
        reset_cancel(thread_id)
        return None

    async def aafter_agent(  # type: ignore[override]
        self,
        state: AgentState[Any],
        runtime: Runtime[ContextT],
    ) -> dict[str, Any] | None:
        del state
        thread_id = self._thread_id(runtime)
        if thread_id is None:
            return None
        lock = self._held_locks.pop(thread_id, None)
        if lock is not None and lock.locked():
            lock.release()
        # Always clear cancel event between turns so a stale signal
        # doesn't leak into the next request.
        reset_cancel(thread_id)
        return None

    # Provide sync no-ops because the middleware base class allows them
    def before_agent(  # type: ignore[override]
        self, state: AgentState[Any], runtime: Runtime[ContextT]
    ) -> dict[str, Any] | None:
        # Sync path: no asyncio.Lock to acquire. Best we can do is reject
        # if anyone else is in flight.
        thread_id = self._thread_id(runtime)
        if thread_id is None:
            if self._require_thread_id:
                raise BusyError("no thread_id configured")
            return None
        lock = manager.lock_for(thread_id)
        if lock.locked():
            raise BusyError(request_id=thread_id)
        return None

    def after_agent(  # type: ignore[override]
        self, state: AgentState[Any], runtime: Runtime[ContextT]
    ) -> dict[str, Any] | None:
        return None


__all__ = [
    "BusyMutexMiddleware",
    "get_cancel_event",
    "manager",
    "request_cancel",
    "reset_cancel",
]
