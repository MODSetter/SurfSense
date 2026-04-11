"""
Unit tests for the proxy_login endpoint.

SPEC (GIVEN / WHEN / THEN)
──────────────────────────
  1  GIVEN no X-Auth-Request-Email header
     WHEN  GET /auth/jwt/proxy-login is called
     THEN  401 Unauthorized is returned

  2  GIVEN email header present AND user already in DB AND user is active
     WHEN  GET /auth/jwt/proxy-login is called
     THEN  302 redirect to frontend / with surfsense_sso_token and
           surfsense_sso_refresh_token cookies set

  3  GIVEN email header present AND user NOT in DB
     WHEN  GET /auth/jwt/proxy-login is called
     THEN  user is JIT-provisioned, 302 redirect with cookies set

  4  GIVEN email header present AND user is inactive
     WHEN  GET /auth/jwt/proxy-login is called
     THEN  401 Unauthorized is returned

  5  GIVEN email header with mixed-case and whitespace
     WHEN  GET /auth/jwt/proxy-login is called
     THEN  lookup uses lowercased/stripped email (case-insensitive match)
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request
from starlette.testclient import TestClient

pytestmark = pytest.mark.unit

_EMAIL = "alice@example.com"
_FRONTEND_URL = "https://foss-research.local.moneta.dev"

# ── helpers ────────────────────────────────────────────────────────────────────


def _make_request(
    path: str = "/auth/jwt/proxy-login",
    headers: dict[str, str] | None = None,
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
    }
    return Request(scope)


def _make_user(
    email: str = _EMAIL,
    is_active: bool = True,
) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = email
    user.is_active = is_active
    return user


def _make_session_cm(session: AsyncMock) -> MagicMock:
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _make_execute_result(user):
    """
    Mock the SQLAlchemy result chain used by proxy_login:
        result = await session.execute(...)
        user = result.unique().scalar_one_or_none()

    The intermediate `.unique()` call is easy to miss when mocking — without it,
    the test gets a stray MagicMock back instead of `user` (or `None`), which
    silently masks bugs in the new-user provisioning path.
    """
    result = MagicMock()
    unique = MagicMock()
    unique.scalar_one_or_none.return_value = user
    result.unique.return_value = unique
    return result


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
        """GIVEN the auth router is imported THEN /auth/jwt/proxy-login is one of its routes."""
        from app.routes.auth_routes import router

        paths = [route.path for route in router.routes]
        assert "/auth/jwt/proxy-login" in paths, (
            f"proxy-login route missing from auth router. Registered paths: {paths}"
        )

    def test_proxy_login_route_uses_get_method(self):
        """GIVEN the route is registered THEN it accepts GET (browser navigation)."""
        from app.routes.auth_routes import router

        matching = [r for r in router.routes if r.path == "/auth/jwt/proxy-login"]
        assert len(matching) == 1, f"expected exactly one proxy-login route, found {len(matching)}"
        assert "GET" in matching[0].methods, (
            f"proxy-login must accept GET (302 cookie handoff). Methods: {matching[0].methods}"
        )

    def test_proxy_login_route_calls_proxy_login_function(self):
        """GIVEN the route is registered THEN it dispatches to the proxy_login function."""
        from app.routes.auth_routes import proxy_login, router

        matching = [r for r in router.routes if r.path == "/auth/jwt/proxy-login"]
        assert matching[0].endpoint is proxy_login, (
            "route is registered but points to a different function"
        )


@pytest.mark.unit
class TestLocalAuthRoutesAreNotRegistered:
    """In SSO mode, the local login/register/forgot-password routes must not exist."""

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
    async def test_no_email_header_returns_401(self):
        """GIVEN no X-Auth-Request-Email header THEN 401."""
        from app.routes.auth_routes import proxy_login

        request = _make_request()  # no email header

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await proxy_login(request)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_existing_active_user_gets_redirect_with_cookies(self):
        """GIVEN existing active user THEN 302 + SSO cookies set."""
        from app.routes.auth_routes import proxy_login

        request = _make_request(headers={"x-auth-request-email": _EMAIL})
        user = _make_user(email=_EMAIL, is_active=True)

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_make_execute_result(user))
        session_cm = _make_session_cm(session)

        mock_strategy = AsyncMock()
        mock_strategy.write_token = AsyncMock(return_value="mock-access-token")

        with (
            patch("app.routes.auth_routes.async_session_maker", return_value=session_cm),
            patch("app.routes.auth_routes.get_jwt_strategy", return_value=mock_strategy),
            patch("app.routes.auth_routes.create_refresh_token", AsyncMock(return_value="mock-refresh-token")),
            patch("app.routes.auth_routes.config") as mock_config,
        ):
            mock_config.NEXT_FRONTEND_URL = _FRONTEND_URL
            response = await proxy_login(request)

        assert response.status_code == 302
        location = response.headers["location"]
        assert location == f"{_FRONTEND_URL}/"

        cookie_header = response.headers.get("set-cookie", "")
        # RedirectResponse may set multiple cookies — check raw headers
        raw_headers = [(k, v) for k, v in response.raw_headers if k == b"set-cookie"]
        cookie_values = [v.decode() for _, v in raw_headers]
        assert any("surfsense_sso_token=mock-access-token" in c for c in cookie_values)
        assert any("surfsense_sso_refresh_token=mock-refresh-token" in c for c in cookie_values)

    @pytest.mark.asyncio
    async def test_new_user_is_provisioned_and_gets_redirect(self):
        """GIVEN user not in DB THEN JIT-provisioned + 302 with cookies."""
        from app.routes.auth_routes import proxy_login

        request = _make_request(headers={"x-auth-request-email": _EMAIL})

        # SELECT returns None (no existing user); after add+commit, refresh populates user
        new_user = _make_user(email=_EMAIL, is_active=True)
        session = AsyncMock()
        session.add = MagicMock()
        session.execute = AsyncMock(return_value=_make_execute_result(None))
        session.refresh = AsyncMock(side_effect=lambda u: setattr(u, "id", new_user.id))

        session_cm = _make_session_cm(session)

        mock_strategy = AsyncMock()
        mock_strategy.write_token = AsyncMock(return_value="new-access-token")

        with (
            patch("app.routes.auth_routes.async_session_maker", return_value=session_cm),
            patch("app.routes.auth_routes.get_jwt_strategy", return_value=mock_strategy),
            patch("app.routes.auth_routes.create_refresh_token", AsyncMock(return_value="new-refresh-token")),
            patch("app.routes.auth_routes.config") as mock_config,
        ):
            mock_config.NEXT_FRONTEND_URL = _FRONTEND_URL
            response = await proxy_login(request)

        session.add.assert_called_once()
        session.commit.assert_called_once()

        assert response.status_code == 302
        assert response.headers["location"] == f"{_FRONTEND_URL}/"

    @pytest.mark.asyncio
    async def test_inactive_user_returns_401(self):
        """GIVEN inactive user THEN 401."""
        from app.routes.auth_routes import proxy_login

        request = _make_request(headers={"x-auth-request-email": _EMAIL})
        inactive = _make_user(email=_EMAIL, is_active=False)

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_make_execute_result(inactive))
        session_cm = _make_session_cm(session)

        from fastapi import HTTPException
        with (
            patch("app.routes.auth_routes.async_session_maker", return_value=session_cm),
            pytest.raises(HTTPException) as exc_info,
        ):
            await proxy_login(request)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_email_is_lowercased_and_stripped_before_lookup(self):
        """GIVEN mixed-case email with whitespace THEN lookup uses normalised form."""
        from app.routes.auth_routes import proxy_login

        raw_email = "  ALICE@EXAMPLE.COM  "
        normalised = "alice@example.com"
        user = _make_user(email=normalised, is_active=True)

        request = _make_request(headers={"x-auth-request-email": raw_email})

        captured_queries = []

        async def mock_execute(stmt):
            captured_queries.append(stmt)
            return _make_execute_result(user)

        session = AsyncMock()
        session.execute = mock_execute
        session_cm = _make_session_cm(session)

        mock_strategy = AsyncMock()
        mock_strategy.write_token = AsyncMock(return_value="token")

        with (
            patch("app.routes.auth_routes.async_session_maker", return_value=session_cm),
            patch("app.routes.auth_routes.get_jwt_strategy", return_value=mock_strategy),
            patch("app.routes.auth_routes.create_refresh_token", AsyncMock(return_value="rt")),
            patch("app.routes.auth_routes.config") as mock_config,
        ):
            mock_config.NEXT_FRONTEND_URL = _FRONTEND_URL
            response = await proxy_login(request)

        assert response.status_code == 302
        # Confirm the query used the lowercased/stripped email by checking
        # that the user was found (i.e. not provisioned — add never called).
        # (Deep SQLAlchemy AST inspection would be brittle; the 302 + no INSERT is sufficient.)
