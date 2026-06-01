"""In-process pub/sub. Streams :class:`Event` values from producers to listeners.

Boundary-crossing (Celery, DB, workers) is a subscriber's job — e.g. the
``event`` trigger enqueues its own task.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from .event import Event

logger = logging.getLogger(__name__)

Subscriber = Callable[[Event], Awaitable[None]]


class EventBus:
    """An in-process pub/sub bus with a per-instance subscriber registry."""

    def __init__(self) -> None:
        self._subscribers: list[Subscriber] = []

    def subscribe(self, handler: Subscriber) -> Subscriber:
        """Register ``handler`` for every event. Idempotent; returns the handler
        so it works as a decorator."""
        if handler not in self._subscribers:
            self._subscribers.append(handler)
        return handler

    def subscribers(self) -> list[Subscriber]:
        """Defensive snapshot of the registered subscribers."""
        return list(self._subscribers)

    async def publish(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        *,
        search_space_id: int,
    ) -> None:
        """Stamp an :class:`Event` and fan it out. Call after your commit."""
        event = Event(
            event_type=event_type,
            payload=payload or {},
            search_space_id=search_space_id,
        )
        await self.dispatch(event)

    async def dispatch(self, event: Event) -> None:
        """Fan ``event`` out concurrently. Subscriber failures are logged and
        isolated; never propagate."""
        subscribers = self.subscribers()
        if not subscribers:
            return

        results = await asyncio.gather(
            *(handler(event) for handler in subscribers),
            return_exceptions=True,
        )

        for handler, result in zip(subscribers, results, strict=True):
            if isinstance(result, Exception):
                logger.error(
                    "event subscriber %r failed for event %s (%s)",
                    getattr(handler, "__qualname__", handler),
                    event.event_id,
                    event.event_type,
                    exc_info=result,
                )


# Process-wide bus. Producers publish to it; subscribers register on it.
bus = EventBus()
