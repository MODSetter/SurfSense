"""Celery telemetry: heartbeat and queue-latency metrics."""

from __future__ import annotations

from functools import lru_cache

from app.observability.signals import metrics as m


def parse_celery_task_label(task_name: str | None) -> str:
    """Return the operation token from a Celery task name."""
    if not task_name:
        return "unknown"
    operation = str(task_name).split("_", 1)[0].strip()
    return operation or "unknown"


@lru_cache(maxsize=1)
def _heartbeat_refreshes():
    return m.get_meter().create_counter(
        "surfsense.celery.heartbeat.refreshes",
        description="Count of SurfSense Celery heartbeat refreshes.",
    )


@lru_cache(maxsize=1)
def _heartbeat_failures():
    return m.get_meter().create_counter(
        "surfsense.celery.heartbeat.failures",
        description="Count of SurfSense Celery heartbeat failures.",
    )


@lru_cache(maxsize=1)
def _queue_latency():
    return m.get_meter().create_histogram(
        "surfsense.celery.queue.latency",
        unit="s",
        description="Time SurfSense Celery tasks spend waiting in queue.",
    )


def record_celery_heartbeat_refresh(*, heartbeat_type: str) -> None:
    m.add(_heartbeat_refreshes(), 1, {"heartbeat.type": heartbeat_type})


def record_celery_heartbeat_failure(*, heartbeat_type: str) -> None:
    m.add(_heartbeat_failures(), 1, {"heartbeat.type": heartbeat_type})


def record_celery_queue_latency(
    duration_s: float,
    *,
    task_name: str | None,
    queue: str | None,
    scheduled: bool,
    operation: str | None,
) -> None:
    m.record(
        _queue_latency(),
        duration_s,
        {
            "task.name": task_name or "unknown",
            "task.queue": queue or "unknown",
            "task.scheduled": bool(scheduled),
            "operation": operation or "unknown",
        },
    )
