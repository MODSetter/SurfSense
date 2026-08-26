"""Knowledge-base telemetry: search/persist spans + search duration metric."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.observability.signals import metrics as m
from app.observability.signals.tracing import span


def kb_search_span(
    *,
    workspace_id: int | None = None,
    query_chars: int | None = None,
    extra: dict[str, Any] | None = None,
):
    attrs: dict[str, Any] = {}
    if workspace_id is not None:
        attrs["workspace.id"] = int(workspace_id)
    if query_chars is not None:
        attrs["query.chars"] = int(query_chars)
    if extra:
        attrs.update(extra)
    return span("kb.search", attributes=attrs)


def rerank_span(*, document_count: int, extra: dict[str, Any] | None = None):
    """Span around one reranker pass over ``document_count`` candidates."""
    attrs: dict[str, Any] = {"rerank.document.count": int(document_count)}
    if extra:
        attrs.update(extra)
    return span("kb.rerank", attributes=attrs)


def kb_persist_span(
    *,
    document_type: str | None = None,
    document_id: int | None = None,
    extra: dict[str, Any] | None = None,
):
    """Span around knowledge-base persistence (NOTE/EXTENSION/FILE)."""
    attrs: dict[str, Any] = {}
    if document_type:
        attrs["document.type"] = document_type
    if document_id is not None:
        attrs["document.id"] = int(document_id)
    if extra:
        attrs.update(extra)
    return span("kb.persist", attributes=attrs)


@lru_cache(maxsize=1)
def _kb_search_duration():
    return m.get_meter().create_histogram(
        "surfsense.kb.search.duration",
        unit="ms",
        description="Duration of SurfSense knowledge-base search calls.",
    )


@lru_cache(maxsize=1)
def _kb_rerank_duration():
    return m.get_meter().create_histogram(
        "surfsense.kb.rerank.duration",
        unit="ms",
        description="Duration of SurfSense reranker passes.",
    )


def record_kb_rerank_duration(duration_ms: float, *, document_count: int) -> None:
    m.record(
        _kb_rerank_duration(), duration_ms, {"rerank.document.batch": document_count > 1}
    )


def record_kb_search_duration(
    duration_ms: float, *, workspace_id: int | None, surface: str
) -> None:
    m.record(
        _kb_search_duration(),
        duration_ms,
        {"workspace.id": workspace_id, "search.surface": surface},
    )
