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
