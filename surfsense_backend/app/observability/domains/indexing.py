"""Indexing telemetry: connector-sync span + document/sync/reconcile/embedding metrics."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.observability.signals import metrics as m
from app.observability.signals.tracing import span


def connector_sync_span(
    *, connector_type: str | None, extra: dict[str, Any] | None = None
):
    """Business-level span around connector indexing task execution."""
    attrs: dict[str, Any] = {"connector.type": connector_type or "unknown"}
    if extra:
        attrs.update(extra)
    return span("connector.sync", attributes=attrs)


@lru_cache(maxsize=1)
def _indexing_document_duration():
    return m.get_meter().create_histogram(
        "surfsense.indexing.document.duration",
        unit="s",
        description="Duration of SurfSense document indexing.",
    )


@lru_cache(maxsize=1)
def _indexing_document_outcome():
    return m.get_meter().create_counter(
        "surfsense.indexing.document.outcome",
        description="Count of SurfSense document indexing outcomes.",
    )


@lru_cache(maxsize=1)
def _connector_sync_duration():
    return m.get_meter().create_histogram(
        "surfsense.connector.sync.duration",
        unit="s",
        description="Duration of SurfSense connector sync tasks.",
    )


@lru_cache(maxsize=1)
def _connector_sync_outcome():
    return m.get_meter().create_counter(
        "surfsense.connector.sync.outcome",
        description="Count of SurfSense connector sync outcomes.",
    )


@lru_cache(maxsize=1)
def _embedding_cache_lookups():
    return m.get_meter().create_counter(
        "surfsense.embedding.cache.lookups",
        description="Count of embedding (chunk+embedding) cache lookups by outcome (hit/miss).",
    )


@lru_cache(maxsize=1)
def _embedding_cache_evictions():
    return m.get_meter().create_counter(
        "surfsense.embedding.cache.evictions",
        description="Count of embedding cache entries evicted, by phase.",
    )


@lru_cache(maxsize=1)
def _chunk_reconcile_chunks():
    return m.get_meter().create_counter(
        "surfsense.indexing.reconcile.chunks",
        description=(
            "Chunks handled by incremental re-indexing, by outcome "
            "(reused/embedded/deleted)."
        ),
    )


def record_indexing_document_duration(
    duration_s: float, *, document_type: str | None
) -> None:
    m.record(
        _indexing_document_duration(),
        duration_s,
        {"document.type": document_type or "unknown"},
    )


def record_indexing_document_outcome(*, document_type: str | None, status: str) -> None:
    m.add(
        _indexing_document_outcome(),
        1,
        {"document.type": document_type or "unknown", "status": status},
    )


def record_connector_sync_duration(
    duration_s: float, *, connector_type: str | None
) -> None:
    m.record(
        _connector_sync_duration(),
        duration_s,
        {"connector.type": connector_type or "unknown"},
    )


def record_connector_sync_outcome(
    *, connector_type: str | None, status: str, error_category: str | None = None
) -> None:
    m.add(
        _connector_sync_outcome(),
        1,
        m.attrs_with_error_category(
            {"connector.type": connector_type or "unknown", "status": status},
            error_category,
        ),
    )


def record_embedding_cache_lookup(
    *, embedding_model: str | None, chunker_kind: str | None, outcome: str
) -> None:
    """Record an embedding-cache lookup. ``outcome`` is ``hit`` or ``miss``."""
    m.add(
        _embedding_cache_lookups(),
        1,
        {
            "embedding.model": embedding_model or "unknown",
            "chunker.kind": chunker_kind or "unknown",
            "outcome": outcome,
        },
    )


def record_embedding_cache_eviction(count: int, *, phase: str) -> None:
    """Record evicted entries. ``phase`` is ``ttl`` or ``size``."""
    if count <= 0:
        return
    m.add(_embedding_cache_evictions(), count, {"phase": phase})


def record_chunk_reconcile(*, reused: int, embedded: int, deleted: int) -> None:
    """Record an incremental re-index: chunks kept vs recomputed."""
    for outcome, count in (
        ("reused", reused),
        ("embedded", embedded),
        ("deleted", deleted),
    ):
        if count > 0:
            m.add(_chunk_reconcile_chunks(), count, {"outcome": outcome})
