"""A worker that sat idle holding the memory its models took exits, and the
supervisor starts a fresh one at once (sidecars/python.ts FRESH_START_EXIT_CODE).

Dropping Docling's converters and the OCR reader in process gave back 160 of
1,620 MB after a scan and a figures pass: torch and the allocator keep the rest.
A new worker holds about 80 MB.
"""

import logging
import signal
import threading
import time
from collections.abc import Callable
from typing import Any

import psutil

log = logging.getLogger(__name__)

FRESH_START_EXIT_CODE = 75
# As sd-server and audio.cpp unload their models: after five idle minutes.
IDLE_SECONDS = 300.0
# A new worker holds about 80 MB and one that only embedded about 250 MB; past
# this it has loaded Docling, the OCR models or Studio's builders.
HELD_BYTES = 400 * 1024 * 1024
CHECK_SECONDS = 30.0


def held_bytes() -> int:
    """What the process holds in memory now, as Task Manager counts it."""
    return psutil.Process().memory_info().rss


class IdleWatch:
    """Whether a worker has done work, does none now, and has not for long enough."""

    def __init__(
        self,
        queue: Any,
        *,
        idle_seconds: float = IDLE_SECONDS,
        held: int = HELD_BYTES,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._idle_seconds = idle_seconds
        self._held = held
        self._clock = clock
        self._lock = threading.Lock()
        self._running = 0
        self._worked = False
        self._last = clock()
        queue.pre_execute(name="fresh-start")(self._began)
        queue.post_execute(name="fresh-start")(self._ended)

    def _began(self, _task: Any) -> None:
        with self._lock:
            self._running += 1
            self._last = self._clock()

    def _ended(self, _task: Any, _value: Any, _error: Any) -> None:
        with self._lock:
            self._running = max(0, self._running - 1)
            self._worked = True
            self._last = self._clock()

    def due(self, now_held: int) -> bool:
        """Only after work, so a worker that holds little never restarts in a loop."""
        with self._lock:
            return (
                self._worked
                and self._running == 0
                and self._clock() - self._last >= self._idle_seconds
                and now_held >= self._held
            )


def watch_for_fresh_start(
    watch: IdleWatch,
    *,
    every: float = CHECK_SECONDS,
    measure: Callable[[], int] = held_bytes,
) -> threading.Event:
    """Ask the consumer to stop once `watch` is due; the returned event says it did.

    The ask is SIGINT, Huey's own graceful stop: the running loop lets every
    thread finish the task it took before `run()` returns, so no dequeued job
    is lost when the process exits.
    """
    asked = threading.Event()

    def check() -> None:
        while not asked.wait(every):
            if watch.due(measure()):
                log.info(
                    "idle and holding %d MB: exiting for a fresh worker",
                    measure() >> 20,
                )
                asked.set()
                signal.raise_signal(signal.SIGINT)

    threading.Thread(target=check, name="fresh-start", daemon=True).start()
    return asked
