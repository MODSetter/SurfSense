"""ETL telemetry: extract/parse/ocr/picture spans + extraction & cache metrics."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.observability.signals import metrics as m
from app.observability.signals.tracing import span


def etl_extract_span(
    *,
    content_type: str | None = None,
    file_extension: str | None = None,
    processing_mode: str | None = None,
    extra: dict[str, Any] | None = None,
):
    """Span around top-level ETL extraction for a file."""
    attrs: dict[str, Any] = {}
    if content_type:
        attrs["content.type"] = content_type
    if file_extension:
        attrs["file.extension"] = file_extension
    if processing_mode:
        attrs["processing.mode"] = processing_mode
    if extra:
        attrs.update(extra)
    return span("etl.extract", attributes=attrs)


def etl_parse_span(
    *,
    etl_service: str | None,
    content_type: str | None = None,
    file_extension: str | None = None,
    processing_mode: str | None = None,
    extra: dict[str, Any] | None = None,
):
    """Span around a concrete ETL parser/backend call."""
    attrs: dict[str, Any] = {"etl.service": etl_service or "unknown"}
    if content_type:
        attrs["content.type"] = content_type
    if file_extension:
        attrs["file.extension"] = file_extension
    if processing_mode:
        attrs["processing.mode"] = processing_mode
    if extra:
        attrs.update(extra)
    return span("etl.parse", attributes=attrs)


def etl_ocr_span(
    *,
    etl_service: str | None,
    file_extension: str | None = None,
    extra: dict[str, Any] | None = None,
):
    """Span around OCR extraction from image content."""
    attrs: dict[str, Any] = {"etl.service": etl_service or "unknown"}
    if file_extension:
        attrs["file.extension"] = file_extension
    if extra:
        attrs.update(extra)
    return span("etl.ocr", attributes=attrs)


def etl_picture_describe_span(
    *, image_count: int | None = None, extra: dict[str, Any] | None = None
):
    """Span around describing embedded images in a document."""
    attrs: dict[str, Any] = {}
    if image_count is not None:
        attrs["image.count"] = int(image_count)
    if extra:
        attrs.update(extra)
    return span("etl.picture.describe", attributes=attrs)


def etl_picture_ocr_span(
    *, file_extension: str | None = None, extra: dict[str, Any] | None = None
):
    """Span around per-image OCR during picture description."""
    attrs: dict[str, Any] = {}
    if file_extension:
        attrs["file.extension"] = file_extension
    if extra:
        attrs.update(extra)
    return span("etl.picture.ocr", attributes=attrs)


@lru_cache(maxsize=1)
def _etl_extract_duration():
    return m.get_meter().create_histogram(
        "surfsense.etl.extract.duration",
        unit="s",
        description="Duration of SurfSense ETL extraction.",
    )


@lru_cache(maxsize=1)
def _etl_extract_outcome():
    return m.get_meter().create_counter(
        "surfsense.etl.extract.outcome",
        description="Count of SurfSense ETL extraction outcomes.",
    )


@lru_cache(maxsize=1)
def _etl_cache_lookups():
    return m.get_meter().create_counter(
        "surfsense.etl.cache.lookups",
        description="Count of ETL parse-cache lookups by outcome (hit/miss).",
    )


@lru_cache(maxsize=1)
def _etl_cache_evictions():
    return m.get_meter().create_counter(
        "surfsense.etl.cache.evictions",
        description="Count of ETL parse-cache entries evicted, by phase.",
    )


def record_etl_extract_duration(
    duration_s: float, *, etl_service: str | None, content_type: str | None, status: str
) -> None:
    m.record(
        _etl_extract_duration(),
        duration_s,
        {
            "etl.service": etl_service or "unknown",
            "content.type": content_type or "unknown",
            "status": status,
        },
    )


def record_etl_extract_outcome(
    *,
    etl_service: str | None,
    content_type: str | None,
    status: str,
    error_category: str | None = None,
) -> None:
    m.add(
        _etl_extract_outcome(),
        1,
        m.attrs_with_error_category(
            {
                "etl.service": etl_service or "unknown",
                "content.type": content_type or "unknown",
                "status": status,
            },
            error_category,
        ),
    )


def record_etl_cache_lookup(
    *, etl_service: str | None, mode: str | None, outcome: str
) -> None:
    """Record a parse-cache lookup. ``outcome`` is ``hit`` or ``miss``."""
    m.add(
        _etl_cache_lookups(),
        1,
        {
            "etl.service": etl_service or "unknown",
            "mode": mode or "unknown",
            "outcome": outcome,
        },
    )


def record_etl_cache_eviction(count: int, *, phase: str) -> None:
    """Record evicted entries. ``phase`` is ``ttl`` or ``size``."""
    if count <= 0:
        return
    m.add(_etl_cache_evictions(), count, {"phase": phase})
