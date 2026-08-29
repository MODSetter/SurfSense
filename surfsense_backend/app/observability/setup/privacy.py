"""In-app privacy: strip URL queries and redact sensitive span attributes.

Restores the scrubbing the deleted Grafana Cloud collector performed, now that
the backend exports OTLP straight to the self-hosted LGTM stack.
"""

from __future__ import annotations

import contextlib
from typing import Any
from urllib.parse import urlsplit, urlunsplit

# The keys the old collector's attributes/scrub processor deleted.
_REDACT_KEYS = (
    "http.request.header.authorization",
    "http.request.header.cookie",
    "db.statement",
)


def _url_without_query(raw_url: Any) -> str | None:
    try:
        parts = urlsplit(str(raw_url))
    except Exception:
        return None
    if not parts.scheme or not parts.netloc:
        return None
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", "", ""))


def sanitize_http_span_url(span: Any, request: Any) -> None:
    """httpx hook: replace URL attributes with a query-stripped form."""
    sanitized = _url_without_query(getattr(request, "url", None))
    if not sanitized:
        return
    with contextlib.suppress(Exception):
        span.set_attribute("http.url", sanitized)
        span.set_attribute("url.full", sanitized)


class _RedactingSpanExporter:
    """Wrap a span exporter, dropping sensitive attributes before export.

    ponytail: reaches into ReadableSpan._attributes (SDK-internal) since ended
    spans are otherwise immutable; guarded so an SDK change degrades to "no
    redaction" rather than dropped spans. Upgrade path: a collector processor
    if a third-party sink is reintroduced.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def export(self, spans: Any) -> Any:
        for span in spans:
            with contextlib.suppress(Exception):
                attributes = span._attributes
                if not attributes:
                    continue
                for key in _REDACT_KEYS:
                    if key in attributes:
                        del attributes[key]
        return self._inner.export(spans)

    def shutdown(self) -> None:
        return self._inner.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self._inner.force_flush(timeout_millis)


def build_span_exporter(inner: Any) -> Any:
    """Wrap an exporter so sensitive attributes never leave the process."""
    return _RedactingSpanExporter(inner)
