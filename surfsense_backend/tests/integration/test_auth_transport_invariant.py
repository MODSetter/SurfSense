from __future__ import annotations

from types import SimpleNamespace

from fastapi import Request, Response

from app.auth.session_cookies import TransportMode, issue, read_refresh
from app.config import config


def _request_with_refresh_cookie(token: str) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/auth/jwt/refresh",
        "headers": [(b"cookie", f"{config.REFRESH_COOKIE_NAME}={token}".encode())],
        "scheme": "https",
        "server": ("testserver", 443),
    }
    return Request(scope)


def test_cookie_transport_sets_cookies_without_body_tokens():
    response = Response()

    body = issue(
        response,
        TransportMode.COOKIE,
        access="access-token",
        refresh="refresh-token",
        access_expires_at=123,
    )

    assert "access_token" not in body
    assert "refresh_token" not in body
    assert body == {"authenticated": True, "access_expires_at": 123}

    set_cookie_headers = response.headers.getlist("set-cookie")
    assert any(config.SESSION_COOKIE_NAME in header for header in set_cookie_headers)
    assert any(config.REFRESH_COOKIE_NAME in header for header in set_cookie_headers)


def test_cookie_transport_re_stamps_access_without_refresh_body_or_cookie():
    response = Response()

    body = issue(
        response,
        TransportMode.COOKIE,
        access="access-token",
        refresh=None,
        access_expires_at=123,
    )

    assert "access_token" not in body
    assert "refresh_token" not in body

    set_cookie_headers = response.headers.getlist("set-cookie")
    assert any(config.SESSION_COOKIE_NAME in header for header in set_cookie_headers)
    assert not any(config.REFRESH_COOKIE_NAME in header for header in set_cookie_headers)


def test_header_transport_returns_body_tokens_without_cookies():
    response = Response()

    body = issue(
        response,
        TransportMode.HEADER,
        access="access-token",
        refresh="refresh-token",
        access_expires_at=123,
    )

    assert body == {
        "access_token": "access-token",
        "refresh_token": "refresh-token",
        "token_type": "bearer",
        "access_expires_at": 123,
    }
    assert "set-cookie" not in response.headers


def test_read_refresh_cookie_source_wins_over_body_source():
    request = _request_with_refresh_cookie("cookie-token")

    refresh, mode = read_refresh(request, SimpleNamespace(refresh_token="body-token"))

    assert refresh == "cookie-token"
    assert mode is TransportMode.COOKIE
