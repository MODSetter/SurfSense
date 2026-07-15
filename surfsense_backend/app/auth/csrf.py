"""CSRF protection for ambient cookie-authenticated requests."""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import config

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _origin_from_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def _allowed_origins() -> set[str]:
    origins = set(config.CSRF_ALLOWED_ORIGINS)
    for url in (config.NEXT_FRONTEND_URL, config.SURFSENSE_PUBLIC_URL):
        origin = _origin_from_url(url)
        if origin:
            origins.add(origin)
    return origins


# Lets self-hosted deployments work from any address (LAN IP, custom domain)
# without pre-configuring the static allowlist on .env.
def _is_same_origin(origin: str | None, host: str | None) -> bool:
    if not origin or not host:
        return False
    parsed_origin = urlparse(origin)
    return parsed_origin.netloc == host


class CsrfOriginMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if request.method not in UNSAFE_METHODS:
            return await call_next(request)

        # PAT/Bearer credentials are not ambient browser credentials and are not
        # CSRF-able. Enforce only when the web session cookie is the credential.
        if (
            request.headers.get("Authorization")
            or config.SESSION_COOKIE_NAME not in request.cookies
        ):
            return await call_next(request)

        origin = request.headers.get("Origin") or _origin_from_url(
            request.headers.get("Referer")
        )
        host = request.headers.get("Host")

        if _is_same_origin(origin, host):
            return await call_next(request)

        if origin not in _allowed_origins():
            return JSONResponse(
                {"detail": "CSRF origin check failed"},
                status_code=status.HTTP_403_FORBIDDEN,
            )

        return await call_next(request)
