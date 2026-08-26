"""Embedding telemetry: generation span + duration (GenAI ``embeddings`` op).

Shared by indexing (document embeds) and retrieval (query embeds); the model
runs in a worker thread, so the span nests under whatever parent enqueued it.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.observability.core import semconv
from app.observability.signals import metrics as m
from app.observability.signals.tracing import SpanKind, span


def embedding_span(
    *, count: int, model: str | None = None, extra: dict[str, Any] | None = None
):
    """Span around one embedding batch (``count`` texts)."""
    attrs: dict[str, Any] = {
        semconv.GEN_AI_OPERATION_NAME: "embeddings",
        "embedding.count": int(count),
    }
    if model:
        attrs[semconv.GEN_AI_REQUEST_MODEL] = model
    if extra:
        attrs.update(extra)
    return span(
        "embedding.generate",
        kind=SpanKind.CLIENT if SpanKind is not None else None,
        attributes=attrs,
    )


@lru_cache(maxsize=1)
def _embedding_duration():
    return m.get_meter().create_histogram(
        "surfsense.embedding.duration",
        unit="ms",
        description="Duration of SurfSense embedding generation calls.",
    )


def record_embedding_duration(
    duration_ms: float, *, model: str | None, count: int
) -> None:
    m.record(
        _embedding_duration(),
        duration_ms,
        {semconv.GEN_AI_REQUEST_MODEL: model, "embedding.batch": count > 1},
    )
