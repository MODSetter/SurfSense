"""Generic span mechanism: create spans, events, and errors."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.observability.core import config
from app.observability.core.attributes import clean_attributes
from app.observability.core.noop import NoopSpan
from app.observability.core.resource import INSTRUMENTATION_NAME, package_version

logger = logging.getLogger(__name__)

try:
    from opentelemetry import trace as _ot_trace
    from opentelemetry.trace import (
        SpanKind,
        Status as _Status,
        StatusCode as _StatusCode,
    )

    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dep
    _ot_trace = None  # type: ignore[assignment]
    SpanKind = None  # type: ignore[assignment]
    _Status = Any  # type: ignore[assignment, misc]
    _StatusCode = Any  # type: ignore[assignment, misc]
    _OTEL_AVAILABLE = False


def _get_tracer():
    if not _OTEL_AVAILABLE:
        return None
    try:
        return _ot_trace.get_tracer(INSTRUMENTATION_NAME, package_version())
    except Exception:  # pragma: no cover - defensive
        return None


@contextmanager
def span(
    name: str,
    *,
    kind: Any | None = None,
    attributes: dict[str, Any] | None = None,
) -> Iterator[Any]:
    """Yield a recording span (or :class:`NoopSpan` when disabled).

    On exception the span records it and is marked ERROR before re-raising.
    """
    if not config.is_enabled():
        yield NoopSpan()
        return

    tracer = _get_tracer()
    if tracer is None:  # pragma: no cover - defensive
        yield NoopSpan()
        return

    start_kwargs: dict[str, Any] = {"kind": kind} if kind is not None else {}
    with tracer.start_as_current_span(name, **start_kwargs) as sp:
        if attributes:
            with contextlib.suppress(Exception):  # pragma: no cover - defensive
                sp.set_attributes(clean_attributes(attributes))
        try:
            yield sp
        except BaseException as exc:
            with contextlib.suppress(Exception):  # pragma: no cover - defensive
                sp.record_exception(exc)
                sp.set_status(_Status(_StatusCode.ERROR, str(exc)))
            raise


def add_event(name: str, attributes: dict[str, Any] | None = None) -> None:
    """Attach an event to the current span; no-op when disabled or not recording."""
    if not config.is_enabled() or _ot_trace is None:
        return
    with contextlib.suppress(Exception):
        sp = _ot_trace.get_current_span()
        if sp is None or not sp.is_recording():
            return
        sp.add_event(name, attributes=clean_attributes(attributes) if attributes else None)


def record_error(span_obj: Any, exc: BaseException) -> None:
    """Record an exception on a span and mark it ERROR without re-raising."""
    if not config.is_enabled():
        return
    with contextlib.suppress(Exception):
        span_obj.record_exception(exc)
        span_obj.set_status(_Status(_StatusCode.ERROR, str(exc)))
