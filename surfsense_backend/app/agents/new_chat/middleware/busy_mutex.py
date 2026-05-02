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
import time
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
        self._cancel_requested_at_ms: dict[str, int] = {}
        self._cancel_attempt_count: dict[str, int] = {}
        # Monotonic per-thread epoch used to prevent stale middleware
        # teardown from releasing a newer turn's lock.
        self._turn_epoch: dict[str, int] = {}

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
            event = asyncio.Event()
            self._cancel_events[thread_id] = event
        event.set()
        now_ms = int(time.time() * 1000)
        self._cancel_requested_at_ms[thread_id] = now_ms
        self._cancel_attempt_count[thread_id] = (
            self._cancel_attempt_count.get(thread_id, 0) + 1
        )
        return True

    def is_cancel_requested(self, thread_id: str) -> bool:
        event = self._cancel_events.get(thread_id)
        return bool(event and event.is_set())

    def cancel_state(self, thread_id: str) -> tuple[int, int] | None:
        if not self.is_cancel_requested(thread_id):
            return None
        attempts = self._cancel_attempt_count.get(thread_id, 1)
        requested_at_ms = self._cancel_requested_at_ms.get(thread_id, 0)
        return attempts, requested_at_ms

    def reset(self, thread_id: str) -> None:
        event = self._cancel_events.get(thread_id)
        if event is not None:
            event.clear()
        self._cancel_requested_at_ms.pop(thread_id, None)
        self._cancel_attempt_count.pop(thread_id, None)

    def bump_turn_epoch(self, thread_id: str) -> int:
        epoch = self._turn_epoch.get(thread_id, 0) + 1
        self._turn_epoch[thread_id] = epoch
        return epoch

    def current_turn_epoch(self, thread_id: str) -> int:
        return self._turn_epoch.get(thread_id, 0)

    def end_turn(self, thread_id: str) -> None:
        """Best-effort terminal cleanup for a thread turn.

        This is intentionally idempotent and safe to call from outer stream
        finally-blocks where middleware teardown might be skipped due to abort
        or disconnect edge-cases.
        """
        # Invalidate any in-flight middleware holder first. This guarantees a
        # stale ``aafter_agent`` from an older attempt cannot unlock a newer
        # retry that already acquired the lock for the same thread.
        self.bump_turn_epoch(thread_id)
        lock = self._locks.get(thread_id)
        if lock is not None and lock.locked():
            lock.release()
        self.reset(thread_id)


# Module-level singleton — process-local but reused across all agent
# instances built in this process. Subagents created in nested
# ``create_agent`` calls also get this so locks are coherent.
manager = _ThreadLockManager()


def get_cancel_event(thread_id: str) -> asyncio.Event:
    """Public accessor used by long-running tools to poll cancellation."""
    return manager.cancel_event(thread_id)


def request_cancel(thread_id: str) -> bool:
    """Trip the cancel event for ``thread_id``. Always returns True."""
    return manager.request_cancel(thread_id)


def is_cancel_requested(thread_id: str) -> bool:
    """Return whether ``thread_id`` currently has a pending cancel signal."""
    return manager.is_cancel_requested(thread_id)


def get_cancel_state(thread_id: str) -> tuple[int, int] | None:
    """Return ``(attempt_count, requested_at_ms)`` for pending cancel state."""
    return manager.cancel_state(thread_id)


def reset_cancel(thread_id: str) -> None:
    """Reset the cancel event for ``thread_id`` (called between turns)."""
    manager.reset(thread_id)


def end_turn(thread_id: str) -> None:
    """Force end-of-turn cleanup for lock + cancel state."""
    manager.end_turn(thread_id)


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
        # Per-call lock ownership tracked as (lock, epoch). ``aafter_agent``
        # only releases when its epoch still matches the manager's current
        # epoch for the thread, preventing stale unlock races.
        self._held_locks: dict[str, tuple[asyncio.Lock, int]] = {}

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
        epoch = manager.bump_turn_epoch(thread_id)
        self._held_locks[thread_id] = (lock, epoch)
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
        held = self._held_locks.pop(thread_id, None)
        if held is None:
            return None
        lock, held_epoch = held
        if held_epoch != manager.current_turn_epoch(thread_id):
            # Stale teardown from an older attempt (e.g. runtime-recovery path
            # already advanced epoch). Do not touch current lock/cancel state.
            return None
        if lock.locked():
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
    "end_turn",
    "get_cancel_event",
    "get_cancel_state",
    "is_cancel_requested",
    "manager",
    "request_cancel",
    "reset_cancel",
]
