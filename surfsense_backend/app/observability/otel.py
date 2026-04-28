"""
OpenTelemetry instrumentation helpers for the SurfSense agent stack.

Tier 3b in the OpenCode-port plan.

Goals
=====

- Provide one tiny, ergonomic API for the spans listed in the plan
  (``tool.call``, ``model.call``, ``kb.search``, ``kb.persist``,
  ``compaction.run``, ``interrupt.raised``, ``permission.asked``).
- Keep span **names** low-cardinality (``tool.call`` rather than
  ``tool.call.<name>``); tool name lives in the ``tool.name`` attribute
  so dashboards aggregate cleanly.
- Default to **no-op** behavior unless ``OTEL_EXPORTER_OTLP_ENDPOINT`` is
  set, OR an external SDK has installed a real ``TracerProvider`` already
  (e.g. via the ``opentelemetry-instrument`` agent).
- Coexist with LangSmith: we never disable LangSmith tracing; we add OTel
  alongside.
- Gracefully degrade if the ``opentelemetry-api`` package is missing.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Lazy/optional OpenTelemetry import
# -----------------------------------------------------------------------------

try:
    from opentelemetry import trace as _ot_trace
    from opentelemetry.trace import (
        Span as _OtSpan,
        Status as _OtStatus,
        StatusCode as _OtStatusCode,
    )

    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover — optional dep
    _ot_trace = None  # type: ignore[assignment]
    _OtSpan = Any  # type: ignore[assignment, misc]
    _OtStatus = Any  # type: ignore[assignment, misc]
    _OtStatusCode = Any  # type: ignore[assignment, misc]
    _OTEL_AVAILABLE = False


_INSTRUMENTATION_NAME = "surfsense.new_chat"
_INSTRUMENTATION_VERSION = "0.1.0"


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------


def _resolve_enabled() -> bool:
    """Return True if OTel spans should actually be emitted."""
    if not _OTEL_AVAILABLE:
        return False
    # Honor an explicit kill-switch first.
    if os.environ.get("SURFSENSE_DISABLE_OTEL", "").lower() in {"1", "true", "yes"}:
        return False
    # Treat a configured endpoint as the canonical "OTel is wired up" signal.
    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return True
    # Or honor an external SDK that already installed a non-default TracerProvider.
    if _ot_trace is not None:
        try:
            provider = _ot_trace.get_tracer_provider()
            # The default proxy provider has no real exporter wired up.
            type_name = type(provider).__name__
            if type_name not in {"ProxyTracerProvider", "NoOpTracerProvider"}:
                return True
        except Exception:  # pragma: no cover — defensive
            return False
    return False


_ENABLED: bool = _resolve_enabled()


def is_enabled() -> bool:
    """Return True if instrumentation is actively emitting spans."""
    return _ENABLED


def _get_tracer():
    if not _OTEL_AVAILABLE:
        return None
    try:
        return _ot_trace.get_tracer(_INSTRUMENTATION_NAME, _INSTRUMENTATION_VERSION)
    except Exception:  # pragma: no cover — defensive
        return None


# -----------------------------------------------------------------------------
# No-op span used when OTel is disabled (avoids a None check at every call site)
# -----------------------------------------------------------------------------


class _NoopSpan:
    """A lightweight stand-in that mimics the subset of ``Span`` we use."""

    def set_attribute(self, key: str, value: Any) -> None:
        return None

    def set_attributes(self, attributes: dict[str, Any]) -> None:
        return None

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        return None

    def record_exception(self, exception: BaseException) -> None:
        return None

    def set_status(self, status: Any) -> None:
        return None


# -----------------------------------------------------------------------------
# Public span helpers
# -----------------------------------------------------------------------------


@contextmanager
def span(
    name: str,
    *,
    attributes: dict[str, Any] | None = None,
) -> Iterator[Any]:
    """Generic span context manager.

    Yields the underlying span (or a :class:`_NoopSpan` when disabled)
    so callers can attach attributes/events incrementally.

    On exception, the span records the error via :meth:`record_exception`
    and sets ``StatusCode.ERROR``; the exception is then re-raised.
    """
    if not _ENABLED:
        yield _NoopSpan()
        return

    tracer = _get_tracer()
    if tracer is None:  # pragma: no cover — defensive
        yield _NoopSpan()
        return

    with tracer.start_as_current_span(name) as sp:
        if attributes:
            try:
                sp.set_attributes(attributes)
            except Exception:  # pragma: no cover — defensive
                pass
        try:
            yield sp
        except BaseException as exc:
            try:
                sp.record_exception(exc)
                sp.set_status(_OtStatus(_OtStatusCode.ERROR, str(exc)))
            except Exception:  # pragma: no cover — defensive
                pass
            raise


# -----------------------------------------------------------------------------
# Domain-specific shortcuts (mirror the plan's enumerated span list)
# -----------------------------------------------------------------------------


def tool_call_span(
    tool_name: str,
    *,
    input_size: int | None = None,
    extra: dict[str, Any] | None = None,
):
    """Span for an individual tool execution.

    Span name is the constant ``tool.call`` (low-cardinality); the tool
    identifier lives in the ``tool.name`` attribute.
    """
    attrs: dict[str, Any] = {"tool.name": tool_name}
    if input_size is not None:
        attrs["tool.input.size"] = int(input_size)
    if extra:
        attrs.update(extra)
    return span("tool.call", attributes=attrs)


def model_call_span(
    *,
    model_id: str | None = None,
    provider: str | None = None,
    extra: dict[str, Any] | None = None,
):
    """Span around a single ``astream`` / ``ainvoke`` call to the LLM."""
    attrs: dict[str, Any] = {}
    if model_id:
        attrs["model.id"] = model_id
    if provider:
        attrs["model.provider"] = provider
    if extra:
        attrs.update(extra)
    return span("model.call", attributes=attrs)


def kb_search_span(
    *,
    search_space_id: int | None = None,
    query_chars: int | None = None,
    extra: dict[str, Any] | None = None,
):
    """Span around knowledge-base search routines."""
    attrs: dict[str, Any] = {}
    if search_space_id is not None:
        attrs["search_space.id"] = int(search_space_id)
    if query_chars is not None:
        attrs["query.chars"] = int(query_chars)
    if extra:
        attrs.update(extra)
    return span("kb.search", attributes=attrs)


def kb_persist_span(
    *,
    document_type: str | None = None,
    document_id: int | None = None,
    extra: dict[str, Any] | None = None,
):
    """Span around knowledge-base persistence operations (NOTE/EXTENSION/FILE)."""
    attrs: dict[str, Any] = {}
    if document_type:
        attrs["document.type"] = document_type
    if document_id is not None:
        attrs["document.id"] = int(document_id)
    if extra:
        attrs.update(extra)
    return span("kb.persist", attributes=attrs)


def compaction_span(
    *,
    reason: str | None = None,
    messages_in: int | None = None,
    extra: dict[str, Any] | None = None,
):
    """Span around the compaction (summarization) middleware run."""
    attrs: dict[str, Any] = {}
    if reason:
        attrs["compaction.reason"] = reason
    if messages_in is not None:
        attrs["compaction.messages.in"] = int(messages_in)
    if extra:
        attrs.update(extra)
    return span("compaction.run", attributes=attrs)


def interrupt_span(
    *,
    interrupt_type: str,
    extra: dict[str, Any] | None = None,
):
    """Span recording an interrupt being raised (HITL or permission_ask)."""
    attrs: dict[str, Any] = {"interrupt.type": interrupt_type}
    if extra:
        attrs.update(extra)
    return span("interrupt.raised", attributes=attrs)


def permission_asked_span(
    *,
    permission: str,
    pattern: str | None = None,
    extra: dict[str, Any] | None = None,
):
    """Span recording a permission ask (PermissionMiddleware)."""
    attrs: dict[str, Any] = {"permission.permission": permission}
    if pattern:
        attrs["permission.pattern"] = pattern
    if extra:
        attrs.update(extra)
    return span("permission.asked", attributes=attrs)


# -----------------------------------------------------------------------------
# Test/utility hooks
# -----------------------------------------------------------------------------


def reload_for_tests() -> bool:
    """Re-evaluate :data:`_ENABLED` from the current environment.

    Tests that toggle ``OTEL_EXPORTER_OTLP_ENDPOINT`` or
    ``SURFSENSE_DISABLE_OTEL`` can call this to reset cached state.
    Returns the new value of :func:`is_enabled`.
    """
    global _ENABLED
    _ENABLED = _resolve_enabled()
    return _ENABLED


__all__ = [
    "compaction_span",
    "interrupt_span",
    "is_enabled",
    "kb_persist_span",
    "kb_search_span",
    "model_call_span",
    "permission_asked_span",
    "reload_for_tests",
    "span",
    "tool_call_span",
]
