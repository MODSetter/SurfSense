"""Messaging gateway infrastructure for external chat channels."""

from __future__ import annotations

from fastapi import HTTPException, status

from app.config import config


def require_gateway_enabled() -> None:
    """FastAPI dependency that gates gateway operational routes on the global flag.

    Returns 404 (rather than 503) when ``GATEWAY_ENABLED`` is FALSE so that
    disabling the gateway makes its webhook/OAuth/pairing surface indistinguishable
    from a route that does not exist.
    """

    if not config.GATEWAY_ENABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
