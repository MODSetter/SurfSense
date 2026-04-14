"""
Unit tests for the proxy_login endpoint.

proxy_login does not touch the User table. All provisioning (including
on_after_register side effects — default SearchSpace, RBAC roles, system
prompts) is owned by ProxyAuthMiddleware. This endpoint only reads
request.state.proxy_user (set upstream by the middleware) and issues a JWT
via short-lived cookies.

SPEC (GIVEN / WHEN / THEN)
──────────────────────────
  1  GIVEN request.state.proxy_user is unset
     WHEN  GET /auth/jwt/proxy-login is called
     THEN  401 Unauthorized is returned

  2  GIVEN request.state.proxy_user is an active user
     WHEN  GET /auth/jwt/proxy-login is called
     THEN  302 redirect to frontend / with surfsense_sso_token and
           surfsense_sso_refresh_token cookies set

  3  GIVEN request.state.proxy_user is an inactive user
     WHEN  GET /auth/jwt/proxy-login is called
     THEN  401 Unauthorized is returned (defence-in-depth; middleware
           normally filters inactive users before this point)
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request

pytestmark = pytest.mark.unit

_EMAIL = "alice@example.com"
_FRONTEND_URL = "https://foss-research.local.moneta.dev"

# ── helpers ────────────────────────────────────────────────────────────────────


def _make_request(
    path: str = "/auth/jwt/proxy-login",
    headers: dict[str, str] | None = None,
    proxy_user=None,
    scheme: str = "https",
) -> Request:
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": raw_headers,
        "query_string": b"",
        "root_path": "",
        "server": ("localhost", 80),
        "scheme": scheme,
    }
    request = Request(scope)
    if proxy_user is not None:
        request.state.proxy_user = proxy_user
    return request


def _make_user(email: str = _EMAIL, is_active: bool = True) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = email
    user.is_active = is_active
    return user


# ── tests ──────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestProxyLoginRouteRegistration:
    """
    Regression guard for the route being missing from the running image.

    These tests don't exercise behaviour — they assert that the router exposes
    the endpoint at the expected path/method. They would have failed loudly when
    the baked Docker image lacked the proxy_login function entirely (the bug
    that caused the cookie-handoff loop in the devstack on 2026-04-11).
    """

    def test_proxy_login_route_is_registered(self):
        from app.routes.auth_routes import router

        paths = [route.path for route in router.routes]
        assert "/auth/jwt/proxy-login" in paths, (
            f"proxy-login route missing from auth router. Registered paths: {paths}"
        )

    def test_proxy_login_route_uses_get_method(self):
        from app.routes.auth_routes import router

        matching = [r for r in router.routes if r.path == "/auth/jwt/proxy-login"]
        assert len(matching) == 1
        assert "GET" in matching[0].methods

    def test_proxy_login_route_calls_proxy_login_function(self):
        from app.routes.auth_routes import proxy_login, router

        matching = [r for r in router.routes if r.path == "/auth/jwt/proxy-login"]
        assert matching[0].endpoint is proxy_login


@pytest.mark.unit
class TestLocalAuthRoutesAreNotRegistered:
    """This fork is SSO-only — native fastapi-users routers must never exist."""

    def test_local_auth_routes_are_not_registered(self):
        from app.app import app

        registered = {
            (method, route.path)
            for route in app.routes
            if hasattr(route, "methods") and hasattr(route, "path")
            for method in (route.methods or ())
        }

        forbidden = {
            ("POST", "/auth/jwt/login"),
            ("POST", "/auth/register"),
            ("POST", "/auth/forgot-password"),
            ("POST", "/auth/reset-password"),
            ("POST", "/auth/request-verify-token"),
            ("POST", "/auth/verify"),
        }

        present = forbidden & registered
        assert not present, (
            f"SSO contract violated — these local-auth routes are registered: {sorted(present)}"
        )


@pytest.mark.unit
class TestProxyLogin:
    @pytest.mark.asyncio
    async def test_no_proxy_user_returns_401(self):
        """GIVEN request.state.proxy_user unset THEN 401."""
        from fastapi import HTTPException

        from app.routes.auth_routes import proxy_login

        request = _make_request()  # no proxy_user
        with pytest.raises(HTTPException) as exc_info:
            await proxy_login(request)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_active_user_gets_redirect_with_cookies(self):
        """GIVEN active proxy_user THEN 302 + SSO cookies, DB never touched."""
        from app.routes.auth_routes import proxy_login

        user = _make_user(is_active=True)
        request = _make_request(proxy_user=user)

        mock_strategy = AsyncMock()
        mock_strategy.write_token = AsyncMock(return_value="mock-access-token")

        with (
            patch(
                "app.routes.auth_routes.get_jwt_strategy", return_value=mock_strategy
            ),
            patch(
                "app.routes.auth_routes.create_refresh_token",
                AsyncMock(return_value="mock-refresh-token"),
            ),
            patch("app.routes.auth_routes.config") as mock_config,
            patch("app.routes.auth_routes.async_session_maker") as mock_sm,
        ):
            mock_config.NEXT_FRONTEND_URL = _FRONTEND_URL
            response = await proxy_login(request)

        mock_sm.assert_not_called()
        assert response.status_code == 302
        assert response.headers["location"] == f"{_FRONTEND_URL}/"

        raw_headers = [(k, v) for k, v in response.raw_headers if k == b"set-cookie"]
        cookie_values = [v.decode() for _, v in raw_headers]
        assert any("surfsense_sso_token=mock-access-token" in c for c in cookie_values)
        assert any(
            "surfsense_sso_refresh_token=mock-refresh-token" in c for c in cookie_values
        )

    @pytest.mark.asyncio
    async def test_inactive_proxy_user_returns_401(self):
        """GIVEN inactive proxy_user THEN 401."""
        from fastapi import HTTPException

        from app.routes.auth_routes import proxy_login

        request = _make_request(proxy_user=_make_user(is_active=False))
        with pytest.raises(HTTPException) as exc_info:
            await proxy_login(request)

        assert exc_info.value.status_code == 401
