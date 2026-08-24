"""Provider-agnostic session registry.

Promoted from the Daytona-specific ``filesystem/sandbox.py``: the per-thread
cache and per-thread lock are proven code, kept intact. Added here: an idle-TTL
reaper and a per-workspace concurrency cap.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from dataclasses import dataclass, field

from app.config import config as app_config

from .protocol import SandboxProvider, SandboxSession, SandboxUnavailableError

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _Entry:
    session: SandboxSession
    workspace_id: str
    last_used: float = field(default_factory=time.monotonic)


class SandboxRegistry:
    """Owns one session per thread for the lifetime of this process."""

    def __init__(
        self,
        provider: SandboxProvider,
        *,
        idle_ttl_seconds: int | None = None,
        max_sessions_per_workspace: int | None = None,
    ) -> None:
        self._provider = provider
        self._idle_ttl = (
            idle_ttl_seconds
            if idle_ttl_seconds is not None
            else app_config.SANDBOX_IDLE_TTL_SECONDS
        )
        self._max_per_workspace = (
            max_sessions_per_workspace
            if max_sessions_per_workspace is not None
            else app_config.SANDBOX_MAX_SESSIONS_PER_WORKSPACE
        )
        self._entries: dict[str, _Entry] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._locks_mu = asyncio.Lock()
        # Capacity is shared across thread locks. Without this lock, two new
        # threads can both observe one free slot and exceed the workspace cap.
        self._capacity_mu = asyncio.Lock()
        # Fire-and-forget terminations would otherwise be collected mid-flight.
        self._pending: set[asyncio.Task] = set()

    async def _lock_for(self, thread_id: str) -> asyncio.Lock:
        async with self._locks_mu:
            lock = self._locks.get(thread_id)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[thread_id] = lock
            return lock

    def _detach(self, thread_id: str, session: SandboxSession) -> None:
        """Kill *session* in the background; the caller has already dropped it."""
        task = asyncio.create_task(self._terminate_quietly(thread_id, session))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def _terminate_quietly(self, thread_id: str, session: SandboxSession) -> None:
        try:
            await session.terminate()
            logger.info("Terminated sandbox session for thread %s", thread_id)
        except Exception:
            logger.debug(
                "Could not terminate session for thread %s", thread_id, exc_info=True
            )

    def _reap_idle(self) -> None:
        """Drop entries idle past the TTL.

        ponytail: swept on access rather than by a background loop, so an idle
        session survives until the next registry call anywhere in the process.
        The sandbox's own server-side timeout is the real backstop; upgrade path
        is a periodic task started at app startup.
        """
        cutoff = time.monotonic() - self._idle_ttl
        for thread_id in [
            tid for tid, e in self._entries.items() if e.last_used < cutoff
        ]:
            entry = self._entries.pop(thread_id)
            logger.info("Reaping idle sandbox for thread %s", thread_id)
            self._detach(thread_id, entry.session)

    def _check_capacity(self, thread_id: str, workspace_id: str) -> None:
        live = sum(
            1
            for tid, e in self._entries.items()
            if e.workspace_id == workspace_id and tid != thread_id
        )
        if live >= self._max_per_workspace:
            raise SandboxUnavailableError(
                "Sandbox limit reached for this workspace — another conversation "
                "is using them. Retry shortly."
            )

    async def get_session(
        self, thread_id: int | str, workspace_id: int | str
    ) -> SandboxSession:
        """Return this thread's session, creating one on first use."""
        key = str(thread_id)
        workspace_key = str(workspace_id)
        lock = await self._lock_for(key)

        async with lock:
            entry = self._entries.get(key)
            if entry is not None:
                entry.last_used = time.monotonic()
                return entry.session

            async with self._capacity_mu:
                # A different thread may have filled the workspace while this
                # one waited. Reap and count atomically with session creation.
                self._reap_idle()
                self._check_capacity(key, workspace_key)
                session = await self._provider.get_or_create_session(key)
                self._entries[key] = _Entry(session=session, workspace_id=workspace_key)
                return session

    def get_cached(self, thread_id: int | str) -> SandboxSession | None:
        """Return the thread's live session, or None. Never creates one.

        Cleanup paths use this: creating a sandbox to salvage files from a
        sandbox that no longer exists would hand back an empty one.
        """
        entry = self._entries.get(str(thread_id))
        return entry.session if entry is not None else None

    async def evict(self, thread_id: int | str) -> None:
        """Forget the thread's session without killing the sandbox.

        Used by the retry path: the next call re-adopts the live sandbox by
        metadata, or creates a fresh one if it is genuinely gone.
        """
        key = str(thread_id)
        lock = await self._lock_for(key)
        async with lock:
            self._entries.pop(key, None)

    async def terminate(self, thread_id: int | str) -> None:
        """Kill the thread's sandbox and forget it. Safe when none exists."""
        key = str(thread_id)
        lock = await self._lock_for(key)
        async with lock:
            self._entries.pop(key, None)
            with contextlib.suppress(Exception):
                await self._provider.terminate_session(key)

    async def aclose(self) -> None:
        """Drain background terminations. For tests and shutdown."""
        pending = list(self._pending)
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)


_registry: SandboxRegistry | None = None
_registry_mu = asyncio.Lock()


def reset_registry_for_new_event_loop() -> None:
    """Drop loop-bound local handles before a fresh-loop Celery task.

    Remote sandboxes remain discoverable by provider metadata. The next access
    adopts one when appropriate, while constructing SDK clients and asyncio
    locks on the current task's loop.
    """
    global _registry, _registry_mu
    _registry = None
    _registry_mu = asyncio.Lock()


async def get_registry() -> SandboxRegistry:
    """Process-wide registry, built from config on first use.

    Refuses while code execution is off. Callers gate too — a disabled
    deployment should never offer the tool in the first place — but that gate
    lives in whichever module registers the tool, so this is the one place the
    invariant holds for every caller, present and future.
    """
    if not app_config.SANDBOX_ENABLED:
        raise SandboxUnavailableError("Code execution is disabled in this deployment.")
    global _registry
    async with _registry_mu:
        if _registry is None:
            from .factory import build_provider

            _registry = SandboxRegistry(build_provider())
        return _registry
