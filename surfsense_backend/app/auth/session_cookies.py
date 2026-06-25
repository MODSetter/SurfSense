"""Centralized session-cookie I/O for web authentication."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import jwt
from fastapi import Request, Response

from app.config import config


class TransportMode(Enum):
    COOKIE = "cookie"
    HEADER = "header"


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
    refresh: str | None = None,
    request: Request | None = None,
) -> None:
    _set_persistent_cookie(
        response,
        key=config.SESSION_COOKIE_NAME,
        value=access,
        max_age=config.ACCESS_TOKEN_LIFETIME_SECONDS,
        request=request,
    )
    if refresh is not None:
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


def read_refresh(
    request: Request, body: Any | None = None
) -> tuple[str | None, TransportMode]:
    cookie = request.cookies.get(config.REFRESH_COOKIE_NAME)
    if cookie:
        return cookie, TransportMode.COOKIE
    if body is None:
        return None, TransportMode.HEADER
    return getattr(body, "refresh_token", None), TransportMode.HEADER


def access_expires_at(access_token: str) -> int:
    payload = jwt.decode(
        access_token,
        config.SECRET_KEY,
        algorithms=["HS256"],
        options={"verify_aud": False},
    )
    return int(payload["exp"])


def issue(
    response: Response,
    mode: TransportMode,
    *,
    access: str,
    refresh: str | None,
    access_expires_at: int,
    request: Request | None = None,
) -> dict:
    if mode is TransportMode.COOKIE:
        write_session(response, access, refresh, request)
        return {"authenticated": True, "access_expires_at": access_expires_at}

    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "access_expires_at": access_expires_at,
    }
