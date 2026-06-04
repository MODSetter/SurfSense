"""TTL-LRU cache for compiled SurfSense deep agents.

Why this exists
---------------

``create_surfsense_deep_agent`` runs a 4-5 second pipeline on EVERY chat
turn:

1. Discover connectors & document types from Postgres (~50-200ms)
2. Build the tool list (built-in + MCP) (~200ms-1.7s)
3. Compose the system prompt
4. Construct ~15 middleware instances (CPU)
5. Eagerly compile the general-purpose subagent
   (``SubAgentMiddleware.__init__`` calls ``create_agent`` synchronously,
   which builds a second LangGraph + Pydantic schemas — ~1.5-2s of pure
   CPU work)
6. Compile the outer LangGraph

For a single thread, all six steps produce the SAME object on every turn
unless the user has changed their LLM config, toggled a feature flag,
added a connector, etc. The right answer is to compile ONCE per
"agent shape" and reuse the resulting :class:`CompiledStateGraph` for
every subsequent turn on the same thread.

Why a per-thread key (not a global pool)
----------------------------------------

Most middleware in the SurfSense stack captures per-thread state in
``__init__`` closures (``thread_id``, ``user_id``, ``search_space_id``,
``filesystem_mode``, ``mentioned_document_ids``). Cross-thread reuse
would silently leak state across users and threads. Keying the cache on
``(llm_config_id, thread_id, ...)`` gives us safe reuse for repeated
turns on the same thread without changing any middleware's behavior.

Phase 2 will move those captured fields onto :class:`SurfSenseContextSchema`
(read via ``runtime.context``) so the cache can collapse to a single
``(llm_config_id, search_space_id, ...)`` key shared across threads. Until
then, per-thread keying is the only safe option.

Cache shape
-----------

* TTL-LRU: entries auto-expire after ``ttl_seconds`` (default 1800s, 30
  minutes — matches a typical chat session). ``maxsize`` (default 256)
  caps memory; LRU evicts least-recently-used on overflow.
* In-flight de-duplication: per-key :class:`asyncio.Lock` so concurrent
  cold misses on the same key wait for the first build instead of
  building N times.
* Process-local: this is an in-memory cache. Multi-replica deployments
  pay the build cost once per replica per key. That's fine; the working
  set per replica is small (one entry per active thread on that replica).

Telemetry
---------

Every lookup logs ``[agent_cache]`` lines through ``surfsense.perf``:

  * ``hit`` — cache hit, microseconds-fast
  * ``miss`` — first build for this key, includes build duration
  * ``stale`` — entry was found but expired; rebuilt
  * ``evict`` — LRU eviction (size-limited)
  * ``size`` — current cache occupancy at lookup time
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.utils.perf import get_perf_logger

logger = logging.getLogger(__name__)
_perf_log = get_perf_logger()


# ---------------------------------------------------------------------------
# Public API: signature helpers (cache key components)
# ---------------------------------------------------------------------------


def stable_hash(*parts: Any) -> str:
    """Compute a deterministic SHA1 of the str repr of ``parts``.

    Used for cache key components that need a fixed-width representation
    (system prompt, tool list, etc.). SHA1 is fine here — this is not a
    security boundary, just a content fingerprint.
    """
    h = hashlib.sha1(usedforsecurity=False)
    for p in parts:
        h.update(repr(p).encode("utf-8", errors="replace"))
        h.update(b"\x1f")  # ASCII unit separator between parts
    return h.hexdigest()


def tools_signature(
    tools: list[Any] | tuple[Any, ...],
    *,
    available_connectors: list[str] | None,
    available_document_types: list[str] | None,
) -> str:
    """Hash the bound-tool surface for cache-key purposes.

    The signature changes whenever:

    * A tool is added or removed from the bound list (built-in toggles,
      MCP tools loaded for the user changes, gating rules flip, etc.).
    * The available connectors / document types for the search space
      change (new connector added, last connector removed, new document
      type indexed). Because :func:`get_connector_gated_tools` derives
      ``modified_disabled_tools`` from ``available_connectors``, the
      tool surface is technically already covered — but we hash the
      connector list separately so an empty-list "no tools changed"
      situation still rotates the key when, say, the user re-adds a
      connector that gates a tool we were already not exposing.

    Stays stable across:

    * Process restarts (tool names + descriptions are static).
    * Different replicas (everyone gets the same hash for the same
      inputs).
    """
    tool_descriptors = sorted(
        (getattr(t, "name", repr(t)), getattr(t, "description", "")) for t in tools
    )
    connectors = sorted(available_connectors or [])
    doc_types = sorted(available_document_types or [])
    return stable_hash(tool_descriptors, connectors, doc_types)


def flags_signature(flags: Any) -> str:
    """Hash the resolved :class:`AgentFeatureFlags` dataclass.

    Frozen dataclasses are deterministically reprable, so a SHA1 of their
    repr is a stable fingerprint. Restart safe (flags are read once at
    process boot).
    """
    return stable_hash(repr(flags))


def system_prompt_hash(system_prompt: str) -> str:
    """Hash a system prompt string. Cheap, ~30µs for typical prompts."""
    return hashlib.sha1(
        system_prompt.encode("utf-8", errors="replace"),
        usedforsecurity=False,
    ).hexdigest()


# ---------------------------------------------------------------------------
# Cache implementation
# ---------------------------------------------------------------------------


@dataclass
class _Entry:
    value: Any
    created_at: float
    last_used_at: float


class _AgentCache:
    """In-process TTL-LRU cache with per-key in-flight de-duplication.

    NOT THREAD-SAFE in the multithreading sense — designed for a single
    asyncio event loop. Uvicorn runs one event loop per worker process,
    so this is fine; multi-worker deployments simply each maintain their
    own cache.
    """

    def __init__(self, *, maxsize: int, ttl_seconds: float) -> None:
        self._maxsize = maxsize
        self._ttl = ttl_seconds
        self._entries: OrderedDict[str, _Entry] = OrderedDict()
        # One lock per key — guards "build" so concurrent cold misses on
        # the same key wait for the first build instead of all racing.
        self._locks: dict[str, asyncio.Lock] = {}

    def _now(self) -> float:
        return time.monotonic()

    def _is_fresh(self, entry: _Entry) -> bool:
        return (self._now() - entry.created_at) < self._ttl

    def _evict_if_full(self) -> None:
        while len(self._entries) >= self._maxsize:
            evicted_key, _ = self._entries.popitem(last=False)
            self._locks.pop(evicted_key, None)
            _perf_log.info(
                "[agent_cache] evict key=%s reason=lru size=%d",
                _short(evicted_key),
                len(self._entries),
            )

    def _touch(self, key: str, entry: _Entry) -> None:
        entry.last_used_at = self._now()
        self._entries.move_to_end(key, last=True)

    async def get_or_build(
        self,
        key: str,
        *,
        builder: Callable[[], Awaitable[Any]],
    ) -> Any:
        """Return the cached value for ``key`` or call ``builder()`` to make it.

        ``builder`` MUST be idempotent — concurrent cold misses on the
        same key collapse to a single ``builder()`` call (the others
        wait on the in-flight lock and observe the populated entry on
        wake).
        """
        # Fast path: hot hit.
        entry = self._entries.get(key)
        if entry is not None and self._is_fresh(entry):
            self._touch(key, entry)
            _perf_log.info(
                "[agent_cache] hit key=%s age=%.1fs size=%d",
                _short(key),
                self._now() - entry.created_at,
                len(self._entries),
            )
            return entry.value

        # Stale entry — drop it; rebuild below.
        if entry is not None and not self._is_fresh(entry):
            _perf_log.info(
                "[agent_cache] stale key=%s age=%.1fs ttl=%.0fs",
                _short(key),
                self._now() - entry.created_at,
                self._ttl,
            )
            self._entries.pop(key, None)

        # Slow path: serialize concurrent misses for the same key.
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            # Double-check after acquiring the lock — another waiter may
            # have populated the entry while we slept.
            entry = self._entries.get(key)
            if entry is not None and self._is_fresh(entry):
                self._touch(key, entry)
                _perf_log.info(
                    "[agent_cache] hit key=%s age=%.1fs size=%d coalesced=true",
                    _short(key),
                    self._now() - entry.created_at,
                    len(self._entries),
                )
                return entry.value

            t0 = time.perf_counter()
            try:
                value = await builder()
            except BaseException:
                # Don't cache failed builds; let the next caller retry.
                _perf_log.warning(
                    "[agent_cache] build_failed key=%s elapsed=%.3fs",
                    _short(key),
                    time.perf_counter() - t0,
                )
                raise
            elapsed = time.perf_counter() - t0

            # Insert + evict.
            self._evict_if_full()
            now = self._now()
            self._entries[key] = _Entry(value=value, created_at=now, last_used_at=now)
            self._entries.move_to_end(key, last=True)
            _perf_log.info(
                "[agent_cache] miss key=%s build=%.3fs size=%d",
                _short(key),
                elapsed,
                len(self._entries),
            )
            return value

    def invalidate(self, key: str) -> bool:
        """Drop a single entry; return True if anything was removed."""
        removed = self._entries.pop(key, None) is not None
        self._locks.pop(key, None)
        if removed:
            _perf_log.info(
                "[agent_cache] invalidate key=%s size=%d",
                _short(key),
                len(self._entries),
            )
        return removed

    def invalidate_prefix(self, prefix: str) -> int:
        """Drop every entry whose key starts with ``prefix``. Returns count."""
        keys = [k for k in self._entries if k.startswith(prefix)]
        for k in keys:
            self._entries.pop(k, None)
            self._locks.pop(k, None)
        if keys:
            _perf_log.info(
                "[agent_cache] invalidate_prefix prefix=%s removed=%d size=%d",
                _short(prefix),
                len(keys),
                len(self._entries),
            )
        return len(keys)

    def clear(self) -> None:
        n = len(self._entries)
        self._entries.clear()
        self._locks.clear()
        if n:
            _perf_log.info("[agent_cache] clear removed=%d", n)

    def stats(self) -> dict[str, Any]:
        return {
            "size": len(self._entries),
            "maxsize": self._maxsize,
            "ttl_seconds": self._ttl,
        }


def _short(key: str, n: int = 16) -> str:
    """Truncate keys for log lines so they don't blow up log volume."""
    return key if len(key) <= n else f"{key[:n]}..."


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_DEFAULT_MAXSIZE = int(os.getenv("SURFSENSE_AGENT_CACHE_MAXSIZE", "256"))
_DEFAULT_TTL = float(os.getenv("SURFSENSE_AGENT_CACHE_TTL_SECONDS", "1800"))

_cache: _AgentCache = _AgentCache(maxsize=_DEFAULT_MAXSIZE, ttl_seconds=_DEFAULT_TTL)


def get_cache() -> _AgentCache:
    """Return the process-wide compiled-agent cache singleton."""
    return _cache


def reload_for_tests(*, maxsize: int = 256, ttl_seconds: float = 1800.0) -> _AgentCache:
    """Replace the singleton with a fresh cache. Tests only."""
    global _cache
    _cache = _AgentCache(maxsize=maxsize, ttl_seconds=ttl_seconds)
    return _cache


__all__ = [
    "flags_signature",
    "get_cache",
    "reload_for_tests",
    "stable_hash",
    "system_prompt_hash",
    "tools_signature",
]
