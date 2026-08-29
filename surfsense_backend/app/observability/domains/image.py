"""Image-generation telemetry: span + duration for text-to-image calls.

``ImageGenRouterService`` (LiteLLM Router ``aimage_generation``) is the single
chokepoint for every image the product generates, so it's instrumented here
rather than at each caller.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.observability.core import semconv
from app.observability.signals import metrics as m
from app.observability.signals.tracing import SpanKind, span


def image_generation_span(
    *,
    model: str | None = None,
    count: int | None = None,
    extra: dict[str, Any] | None = None,
):
    """Span around one image-generation call (``count`` images requested)."""
    attrs: dict[str, Any] = {semconv.GEN_AI_OPERATION_NAME: "image_generation"}
    if model:
        attrs[semconv.GEN_AI_REQUEST_MODEL] = model
    if count is not None:
        attrs["image.count"] = int(count)
    if extra:
        attrs.update(extra)
    return span(
        "image.generate",
        kind=SpanKind.CLIENT if SpanKind is not None else None,
        attributes=attrs,
    )


@lru_cache(maxsize=1)
def _image_generation_duration():
    return m.get_meter().create_histogram(
        "surfsense.image.generation.duration",
        unit="ms",
        description="Duration of SurfSense image-generation calls.",
    )


def record_image_generation_duration(
    duration_ms: float, *, model: str | None = None
) -> None:
    m.record(
        _image_generation_duration(),
        duration_ms,
        {semconv.GEN_AI_REQUEST_MODEL: model},
    )
