"""Centralized session-cookie I/O for web authentication."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Request, Response

from app.config import config


def _cookie_secure(request: Request | None = None) -> bool:
    policy = config.SESSION_COOKIE_SECURE_POLICY
    if policy == "always":
        return True
    if policy == "never":
        return False
    if request is not None:
        proto = request.headers.get("x-forwarded-proto")
        if proto:
            return proto.split(",", 1)[0].strip().lower() == "https"
        return request.url.scheme == "https"
    return bool(config.BACKEND_URL and config.BACKEND_URL.startswith("https://"))


def _set_persistent_cookie(
    response: Response,
    *,
    key: str,
    value: str,
    max_age: int,
    request: Request | None,
) -> None:
    expires = datetime.now(UTC) + timedelta(seconds=max_age)
    response.set_cookie(
        key=key,
        value=value,
        max_age=max_age,
        expires=expires,
        httponly=True,
        secure=_cookie_secure(request),
        samesite=config.SESSION_COOKIE_SAMESITE,
        domain=config.COOKIE_DOMAIN,
        path="/",
    )


def write_session(
    response: Response,
    access: str,
    refresh: str,
    request: Request | None = None,
) -> None:
    _set_persistent_cookie(
        response,
        key=config.SESSION_COOKIE_NAME,
        value=access,
        max_age=config.ACCESS_TOKEN_LIFETIME_SECONDS,
        request=request,
    )
    _set_persistent_cookie(
        response,
        key=config.REFRESH_COOKIE_NAME,
        value=refresh,
        max_age=config.REFRESH_TOKEN_LIFETIME_SECONDS,
        request=request,
    )


def clear_session(response: Response, request: Request | None = None) -> None:
    for key in (config.SESSION_COOKIE_NAME, config.REFRESH_COOKIE_NAME):
        response.delete_cookie(
            key=key,
            path="/",
            domain=config.COOKIE_DOMAIN,
            secure=_cookie_secure(request),
            samesite=config.SESSION_COOKIE_SAMESITE,
            httponly=True,
        )


def read_refresh(request: Request, body: Any | None = None) -> str | None:
    cookie = request.cookies.get(config.REFRESH_COOKIE_NAME)
    if cookie:
        return cookie
    if body is None:
        return None
    return getattr(body, "refresh_token", None)
