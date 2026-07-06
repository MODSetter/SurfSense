"""In-process pub/sub bus for streaming a scraper run's progress over SSE.

One process, one bus (the module-level :data:`run_event_bus`). Per ``run_id`` it
holds three things:

* a set of subscriber ``asyncio.Queue`` s — one per open SSE connection;
* a bounded ring buffer of recent events so a late/reconnecting subscriber can
  replay what it missed before tailing live;
* the background ``asyncio.Task`` running the scrape, so the cancel endpoint can
  reach it.

State for a run is dropped when it reaches a terminal event (``run.finished``);
a client that connects *after* that reads the final snapshot from the ``runs``
row instead. ``ponytail:`` single-process only — a multi-worker deployment needs
Redis pub/sub (or Postgres LISTEN/NOTIFY) behind this same interface.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = logging.getLogger(__name__)

_BUFFER_SIZE = 500
_SUBSCRIBER_QUEUE_SIZE = 1000


class RunEventBus:
    """Fan-out of per-run progress events to live SSE subscribers."""

    def __init__(self, *, buffer_size: int = _BUFFER_SIZE) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = {}
        self._buffers: dict[str, deque[dict[str, Any]]] = {}
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._buffer_size = buffer_size

    # -- task registry (for cancellation) --------------------------------

    def register_task(self, run_id: str, task: asyncio.Task[Any]) -> None:
        self._tasks[run_id] = task

    def get_task(self, run_id: str) -> asyncio.Task[Any] | None:
        return self._tasks.get(run_id)

    # -- publish / subscribe ---------------------------------------------

    def publish(self, run_id: str, event: dict[str, Any]) -> None:
        """Buffer an event and fan it out to every live subscriber.

        Called from within the event loop by the running scrape. Full
        subscriber queues drop the event rather than block the scrape;
        the replay buffer still preserves recent history.
        """
        buffer = self._buffers.setdefault(run_id, deque(maxlen=self._buffer_size))
        buffer.append(event)
        for queue in list(self._subscribers.get(run_id, ())):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.debug("run %s: subscriber queue full, dropping event", run_id)

    def subscribe(self, run_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=_SUBSCRIBER_QUEUE_SIZE
        )
        self._subscribers.setdefault(run_id, set()).add(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        subscribers = self._subscribers.get(run_id)
        if subscribers is None:
            return
        subscribers.discard(queue)
        if not subscribers:
            self._subscribers.pop(run_id, None)

    def replay(self, run_id: str) -> Iterable[dict[str, Any]]:
        return list(self._buffers.get(run_id, ()))

    def close(self, run_id: str) -> None:
        """Drop all state for a finished run.

        Terminal events are published *before* this, so any live subscriber has
        already received ``run.finished`` in its queue and will break its loop.
        """
        self._buffers.pop(run_id, None)
        self._subscribers.pop(run_id, None)
        self._tasks.pop(run_id, None)


run_event_bus = RunEventBus()
