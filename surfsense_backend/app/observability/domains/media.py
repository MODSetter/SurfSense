"""Media-render telemetry: duration + outcome for podcast/video deliverables.

These run as Celery tasks (already span-covered); the missing signal was an SLI
for these long, credit-consuming renders. ``kind`` separates podcast vs video.
"""

from __future__ import annotations

from functools import lru_cache

from app.observability.signals import metrics as m


@lru_cache(maxsize=1)
def _render_duration():
    return m.get_meter().create_histogram(
        "surfsense.media.render.duration",
        unit="s",
        description="Duration of SurfSense media deliverable renders.",
    )


@lru_cache(maxsize=1)
def _render_outcome():
    return m.get_meter().create_counter(
        "surfsense.media.render.outcome",
        description="Count of SurfSense media render outcomes.",
    )


def record_media_render(
    duration_s: float, *, kind: str, status: str, error_category: str | None = None
) -> None:
    """Record one render. ``kind`` is ``podcast``/``video``; ``status`` is
    ``ready``/``failed``/``superseded``."""
    attrs = {"media.kind": kind, "status": status}
    m.record(_render_duration(), duration_s, attrs)
    m.add(_render_outcome(), 1, m.attrs_with_error_category(attrs, error_category))


@lru_cache(maxsize=1)
def _video_render_duration():
    return m.get_meter().create_histogram(
        "surfsense.video.render.duration",
        unit="s",
        description="Duration of sandbox-native video renders.",
    )


@lru_cache(maxsize=1)
def _video_admission_wait():
    return m.get_meter().create_histogram(
        "surfsense.video.admission.wait",
        unit="s",
        description="Time video renders wait for the per-worker admission gate.",
    )


@lru_cache(maxsize=1)
def _video_segment_count():
    return m.get_meter().create_histogram(
        "surfsense.video.segment.count",
        unit="{segment}",
        description="Rendered segment count per video.",
    )


@lru_cache(maxsize=1)
def _video_verify_failures():
    return m.get_meter().create_counter(
        "surfsense.video.verify.failures",
        description="Count of video verification failures by reason.",
    )


def record_video_render_duration(seconds: float, *, scope: str = "render") -> None:
    m.record(_video_render_duration(), seconds, {"scope": scope})


def record_video_admission_wait(seconds: float, *, queue_depth: int) -> None:
    m.record(_video_admission_wait(), seconds, {"queue.depth": max(0, queue_depth)})


def record_video_segment_count(count: int) -> None:
    m.record(_video_segment_count(), count, {})


def record_video_verify_failure(reason: str) -> None:
    m.add(_video_verify_failures(), 1, {"reason": reason})
