"""Event trigger source: the bus subscriber that enqueues the selector.

Runs in whatever process published the event, so it stays thin — it only hands
the event to a worker (the selector does the DB matching).
"""

from __future__ import annotations

from app.event_bus import Event

TASK_NAME = "automation_event_select"


async def on_event(event: Event) -> None:
    """Enqueue the selector for ``event``."""
    # Lazy import: keeps app.celery_app out of the triggers-package import graph.
    from app.celery_app import celery_app

    celery_app.send_task(TASK_NAME, kwargs={"event": event.model_dump(mode="json")})
