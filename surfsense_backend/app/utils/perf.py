"""
Centralized performance monitoring for SurfSense backend.

Provides:
- A shared [PERF] logger used across all modules
- perf_timer context manager for timing code blocks
- perf_async_timer for async code blocks
- system_snapshot() for CPU/memory profiling
- RequestPerfMiddleware for per-request timing
"""

import gc
import logging
import os
import time
from contextlib import asynccontextmanager, contextmanager
from typing import Any

_perf_log: logging.Logger | None = None
_last_rss_mb: float = 0.0


def get_perf_logger() -> logging.Logger:
    """Return the singleton [PERF] logger, creating it once on first call."""
    global _perf_log
    if _perf_log is None:
        _perf_log = logging.getLogger("surfsense.perf")
        _perf_log.setLevel(logging.DEBUG)
        if not _perf_log.handlers:
            h = logging.StreamHandler()
            h.setFormatter(logging.Formatter("%(asctime)s [PERF] %(message)s"))
            _perf_log.addHandler(h)
            _perf_log.propagate = False
    return _perf_log


@contextmanager
def perf_timer(label: str, *, extra: dict[str, Any] | None = None):
    """Synchronous context manager that logs elapsed wall-clock time.

    Usage:
        with perf_timer("[my_func] heavy computation"):
            ...
    """
    log = get_perf_logger()
    t0 = time.perf_counter()
    yield
    elapsed = time.perf_counter() - t0
    suffix = ""
    if extra:
        suffix = " " + " ".join(f"{k}={v}" for k, v in extra.items())
    log.info("%s in %.3fs%s", label, elapsed, suffix)


@asynccontextmanager
async def perf_async_timer(label: str, *, extra: dict[str, Any] | None = None):
    """Async context manager that logs elapsed wall-clock time.

    Usage:
        async with perf_async_timer("[search] vector search"):
            ...
    """
    log = get_perf_logger()
    t0 = time.perf_counter()
    yield
    elapsed = time.perf_counter() - t0
    suffix = ""
    if extra:
        suffix = " " + " ".join(f"{k}={v}" for k, v in extra.items())
    log.info("%s in %.3fs%s", label, elapsed, suffix)


def system_snapshot() -> dict[str, Any]:
    """Capture a lightweight CPU + memory snapshot of the current process.

    Returns a dict with:
      - rss_mb: Resident Set Size in MB
      - rss_delta_mb: Change in RSS since the last snapshot
      - cpu_percent: CPU usage % since last call (per-process)
      - threads: number of active threads
      - open_fds: number of open file descriptors (Linux only)
      - asyncio_tasks: number of asyncio tasks currently alive
      - gc_counts: tuple of object counts per gc generation
    """
    import asyncio

    global _last_rss_mb

    snapshot: dict[str, Any] = {}
    try:
        import psutil

        proc = psutil.Process(os.getpid())
        mem = proc.memory_info()
        rss_mb = round(mem.rss / 1024 / 1024, 1)
        snapshot["rss_mb"] = rss_mb
        snapshot["rss_delta_mb"] = (
            round(rss_mb - _last_rss_mb, 1) if _last_rss_mb else 0.0
        )
        _last_rss_mb = rss_mb
        snapshot["cpu_percent"] = proc.cpu_percent(interval=None)
        snapshot["threads"] = proc.num_threads()
        try:
            snapshot["open_fds"] = proc.num_fds()
        except AttributeError:
            snapshot["open_fds"] = -1
    except ImportError:
        snapshot["rss_mb"] = -1
        snapshot["rss_delta_mb"] = 0.0
        snapshot["cpu_percent"] = -1
        snapshot["threads"] = -1
        snapshot["open_fds"] = -1

    try:
        all_tasks = asyncio.all_tasks()
        snapshot["asyncio_tasks"] = len(all_tasks)
    except RuntimeError:
        snapshot["asyncio_tasks"] = -1

    snapshot["gc_counts"] = gc.get_count()

    return snapshot


def log_system_snapshot(label: str = "system_snapshot") -> None:
    """Capture and log a system snapshot with memory delta tracking."""
    snap = system_snapshot()
    delta_str = ""
    if snap["rss_delta_mb"]:
        sign = "+" if snap["rss_delta_mb"] > 0 else ""
        delta_str = f" delta={sign}{snap['rss_delta_mb']}MB"
    get_perf_logger().info(
        "[%s] rss=%.1fMB%s cpu=%.1f%% threads=%d fds=%d asyncio_tasks=%d gc=%s",
        label,
        snap["rss_mb"],
        delta_str,
        snap["cpu_percent"],
        snap["threads"],
        snap["open_fds"],
        snap["asyncio_tasks"],
        snap["gc_counts"],
    )

    if snap["rss_mb"] > 0 and snap["rss_delta_mb"] > 500:
        get_perf_logger().warning(
            "[MEMORY_SPIKE] %s: RSS jumped by %.1fMB (now %.1fMB). "
            "Possible leak — check recent operations.",
            label,
            snap["rss_delta_mb"],
            snap["rss_mb"],
        )


def trim_native_heap() -> bool:
    """Ask glibc to return free heap pages to the OS via ``malloc_trim(0)``.

    On Linux (glibc), ``free()`` does not release memory back to the OS if
    it sits below the brk watermark.  ``malloc_trim`` forces the allocator
    to give back as many freed pages as possible.

    Returns True if trimming was performed, False otherwise (non-Linux or
    libc unavailable).
    """
    import ctypes
    import sys

    if sys.platform != "linux":
        return False
    try:
        libc = ctypes.CDLL("libc.so.6")
        libc.malloc_trim(0)
        return True
    except (OSError, AttributeError):
        return False
