"""Extraction of a SurfSense API key from request headers.

Pure and side-effect free: given the request headers, return the caller's key
or ``None``. Isolated from transport and state so the parsing rules stay
trivially unit-testable.
"""

from __future__ import annotations

from starlette.datastructures import Headers

_BEARER_PREFIX = "bearer "


def extract_api_key(headers: Headers) -> str | None:
    """Return the caller's key from the ``Authorization: Bearer`` slot the
    backend already expects, falling back to ``X-API-Key`` for clients that can
    only send custom headers."""
    authorization = headers.get("authorization", "")
    if authorization[: len(_BEARER_PREFIX)].lower() == _BEARER_PREFIX:
        token = authorization[len(_BEARER_PREFIX) :].strip()
        if token:
            return token

    fallback = headers.get("x-api-key", "").strip()
    return fallback or None
