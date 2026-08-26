"""Low-cardinality exception categorization for telemetry attributes."""

from __future__ import annotations

_ERROR_CATEGORY_UNKNOWN = "unknown"

_ERROR_CATEGORY_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("rate_limited", ("ratelimit", "rate_limit", "toomanyrequests", "429")),
    ("auth_failed", ("authentication", "auth", "unauthorized", "forbidden")),
    ("quota_exhausted", ("quota", "insufficient", "credit", "billing")),
    ("timeout", ("timeout", "timedout", "deadline")),
    ("network_failed", ("connection", "connect", "network", "dns", "socket")),
    ("server_error", ("internalserver", "serviceunavailable", "badgateway", "gateway")),
    ("lock_contention", ("lock", "busy", "contention", "alreadyrunning")),
    ("unsupported_format", ("unsupported", "format", "filetype")),
    ("provider_error", ("provider", "apierror", "apistatus", "badrequest")),
)


def categorize_exception(exc: BaseException | None) -> str:
    """Map an exception to a stable, low-cardinality category token."""
    if exc is None:
        return _ERROR_CATEGORY_UNKNOWN
    haystack = " ".join(
        cls.__name__.replace("-", "").replace("_", "").lower()
        for cls in type(exc).__mro__
    )
    for category, hints in _ERROR_CATEGORY_HINTS:
        if any(hint in haystack for hint in hints):
            return category
    return _ERROR_CATEGORY_UNKNOWN
