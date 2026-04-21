"""
Unit tests for app.middleware.proxy_auth.

SPEC (GIVEN / WHEN / THEN)
──────────────────────────
  1  GIVEN request.state.proxy_user is already set
     WHEN  request arrives
     THEN  call_next is called immediately with no DB access

  2  GIVEN request path is a bypass path
     WHEN  request arrives with email header
     THEN  call_next is called with no DB access, proxy_user not set

  3  GIVEN no X-Auth-Request-Email header
     WHEN  request arrives
     THEN  call_next is called and proxy_user not set

  4  GIVEN email is not in DB (first seen)
     WHEN  request arrives with email header
     THEN  user is inserted, on_after_register is called, proxy_user set

  5  GIVEN email already in DB
     WHEN  request arrives with email header
     THEN  existing user found, no INSERT, proxy_user set

  6  GIVEN user.is_active is False
     WHEN  request arrives with email header
     THEN  proxy_user not set (pass through unauthenticated)

  7  GIVEN valid email header and active user
     WHEN  middleware runs
     THEN  request.state.proxy_user == resolved user

  8  GIVEN email header with uppercase and leading/trailing whitespace
     WHEN  request arrives
     THEN  _normalise_email is called with raw value and normalised email is used

  9  GIVEN concurrent INSERT raises IntegrityError
     WHEN  commit raises IntegrityError
     THEN  fallback SELECT finds user, proxy_user set, no crash
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request
from starlette.responses import Response

from app.middleware.proxy_auth import (
    ProxyAuthMiddleware,
    _coerce_bypass_paths,
    _is_bypass_path,
    _normalise_email,
)

pytestmark = pytest.mark.unit

_EMAIL = "alice@example.com"


# ── shared test helpers ────────────────────────────────────────────────────────


def _make_request(
    path: str = "/api/data",
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
    }
    return Request(scope)


def _make_user(
    email: str = _EMAIL,
    is_active: bool = True,
    last_login: datetime | None = None,
) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = email
    user.is_active = is_active
    user.last_login = last_login
    return user


def _make_middleware(
    bypass_paths: list[str] | None = None,
) -> ProxyAuthMiddleware:
    """Instantiate ProxyAuthMiddleware without calling __init__ (skips config + ASGI setup)."""
    mw = object.__new__(ProxyAuthMiddleware)
    mw.bypass_paths = bypass_paths if bypass_paths is not None else ["/health"]
    return mw


def _make_session_cm(session: AsyncMock) -> MagicMock:
    """Wrap an AsyncMock session in an async context manager mock."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


async def _ok_call_next(request: Request) -> Response:
    return Response("OK")


# ── _normalise_email ───────────────────────────────────────────────────────────


class TestNormaliseEmail:
    def test_lowercases(self):
        assert _normalise_email("ALICE@Example.COM") == "alice@example.com"

    def test_strips_leading_trailing_whitespace(self):
        assert _normalise_email("  alice@example.com  ") == "alice@example.com"

    def test_nfkc_fullwidth_chars(self):
        # Fullwidth 'a' (U+FF41) → ASCII 'a'
        assert _normalise_email("\uff41lice@example.com") == "alice@example.com"

    def test_combined(self):
        assert _normalise_email("  ALICE@EXAMPLE.COM  ") == "alice@example.com"


# ── _is_bypass_path ────────────────────────────────────────────────────────────


class TestIsBypassPath:
    def test_exact_match(self):
        assert _is_bypass_path("/health", ["/health"])

    def test_sub_path(self):
        assert _is_bypass_path("/health/ready", ["/health"])

    def test_no_prefix_collision(self):
        # /healthz must NOT match bypass prefix /health
        assert not _is_bypass_path("/healthz", ["/health"])

    def test_unrelated_path(self):
        assert not _is_bypass_path("/api/users", ["/health"])

    def test_multiple_bypass_paths(self):
        assert _is_bypass_path("/docs", ["/health", "/docs"])

    def test_root_bypass_covers_subpaths(self):
        assert _is_bypass_path("/docs/intro", ["/health", "/docs"])


# ── _coerce_bypass_paths ───────────────────────────────────────────────────────


class TestCoerceBypassPaths:
    def test_none_returns_default(self):
        assert _coerce_bypass_paths(None) == ["/health"]

    def test_empty_string_returns_default(self):
        assert _coerce_bypass_paths("") == ["/health"]

    def test_comma_separated_string(self):
        assert _coerce_bypass_paths("/health,/docs") == ["/health", "/docs"]

    def test_list_passthrough(self):
        assert _coerce_bypass_paths(["/health", "/metrics"]) == [
            "/health",
            "/metrics",
        ]

    def test_strips_spaces_from_csv(self):
        assert _coerce_bypass_paths(" /health , /docs ") == ["/health", "/docs"]


# ── ProxyAuthMiddleware.dispatch ───────────────────────────────────────────────


class TestProxyAuthMiddlewareDispatch:
    # ── SPEC 1: already authenticated ─────────────────────────────────────────

    async def test_already_authenticated_skips_db(self):
        """
        GIVEN  request.state.proxy_user is already set
        WHEN   request arrives
        THEN   call_next is called immediately, DB never touched, original user preserved
        """
        mw = _make_middleware()
        existing = _make_user()
        request = _make_request(headers={"x-auth-request-email": _EMAIL})
        request.state.proxy_user = existing
        call_next = AsyncMock(return_value=Response("OK"))

        with patch("app.middleware.proxy_auth.async_session_maker") as mock_sm:
            await mw.dispatch(request, call_next)

        mock_sm.assert_not_called()
        assert request.state.proxy_user is existing

    # ── SPEC 2: bypass path ────────────────────────────────────────────────────

    async def test_bypass_path_skips_db_and_leaves_user_unset(self):
        """
        GIVEN  path is a configured bypass path (/health)
        WHEN   request arrives with email header
        THEN   call_next called, DB never touched, proxy_user not set
        """
        mw = _make_middleware(bypass_paths=["/health"])
        request = _make_request(
            path="/health",
            headers={"x-auth-request-email": _EMAIL},
        )
        call_next = AsyncMock(return_value=Response("OK"))

        with patch("app.middleware.proxy_auth.async_session_maker") as mock_sm:
            await mw.dispatch(request, call_next)

        mock_sm.assert_not_called()
        assert getattr(request.state, "proxy_user", None) is None

    # ── SPEC 3: no email header ────────────────────────────────────────────────

    async def test_no_email_header_passes_through_unauthenticated(self):
        """
        GIVEN  no X-Auth-Request-Email header
        WHEN   request arrives
        THEN   call_next called, DB never touched, proxy_user not set
        """
        mw = _make_middleware()
        request = _make_request()  # no email header
        call_next = AsyncMock(return_value=Response("OK"))

        with patch("app.middleware.proxy_auth.async_session_maker") as mock_sm:
            await mw.dispatch(request, call_next)

        mock_sm.assert_not_called()
        assert getattr(request.state, "proxy_user", None) is None

    # ── SPEC 4: new user (first seen) ─────────────────────────────────────────

    async def test_new_user_created_and_on_after_register_called(self):
        """
        GIVEN  email not in DB
        WHEN   request arrives with email header
        THEN   User is INSERTed, on_after_register is called, proxy_user set
        """
        mw = _make_middleware()
        request = _make_request(headers={"x-auth-request-email": _EMAIL})

        # Main session: SELECT → None (user absent), then UPDATE last_login
        s1 = AsyncMock()
        s1.add = MagicMock()  # add() is sync; avoid AsyncMock warning
        no_user_result = MagicMock()
        no_user_result.unique.return_value.scalar_one_or_none.return_value = None
        update_result = MagicMock()
        s1.execute = AsyncMock(side_effect=[no_user_result, update_result])
        s1_cm = _make_session_cm(s1)

        # Registration session: re-fetch user by id for on_after_register
        reg_user = _make_user(email=_EMAIL)
        s2 = AsyncMock()
        reg_result = MagicMock()
        reg_result.unique.return_value.scalar_one_or_none.return_value = reg_user
        s2.execute = AsyncMock(return_value=reg_result)
        s2_cm = _make_session_cm(s2)

        mock_on_after_register = AsyncMock()
        mock_manager = MagicMock()
        mock_manager.on_after_register = mock_on_after_register

        with (
            patch(
                "app.middleware.proxy_auth.async_session_maker",
                side_effect=[s1_cm, s2_cm],
            ),
            patch("app.users.UserManager", return_value=mock_manager),
            patch("app.middleware.proxy_auth.SQLAlchemyUserDatabase"),
        ):
            await mw.dispatch(request, _ok_call_next)

        s1.add.assert_called_once()
        s1.commit.assert_called()
        mock_on_after_register.assert_called_once()
        assert getattr(request.state, "proxy_user", None) is not None

    # ── SPEC 5: existing user ──────────────────────────────────────────────────

    async def test_existing_user_found_no_insert(self):
        """
        GIVEN  email already in DB
        WHEN   request arrives with email header
        THEN   user found by SELECT, no INSERT (session.add not called), proxy_user set
        """
        mw = _make_middleware()
        existing = _make_user(email=_EMAIL, last_login=None)
        request = _make_request(headers={"x-auth-request-email": _EMAIL})

        session = AsyncMock()
        found_result = MagicMock()
        found_result.unique.return_value.scalar_one_or_none.return_value = existing
        update_result = MagicMock()
        session.execute = AsyncMock(side_effect=[found_result, update_result])
        session_cm = _make_session_cm(session)

        with patch(
            "app.middleware.proxy_auth.async_session_maker", return_value=session_cm
        ):
            await mw.dispatch(request, _ok_call_next)

        session.add.assert_not_called()
        assert request.state.proxy_user is existing

    # ── SPEC 6: inactive user ──────────────────────────────────────────────────

    async def test_inactive_user_passes_through_unauthenticated(self):
        """
        GIVEN  user exists but is_active=False
        WHEN   request arrives with email header
        THEN   proxy_user not set (inactive user is not injected)
        """
        mw = _make_middleware()
        inactive = _make_user(email=_EMAIL, is_active=False)
        request = _make_request(headers={"x-auth-request-email": _EMAIL})

        session = AsyncMock()
        found_result = MagicMock()
        found_result.unique.return_value.scalar_one_or_none.return_value = inactive
        session.execute = AsyncMock(return_value=found_result)
        session_cm = _make_session_cm(session)

        with patch(
            "app.middleware.proxy_auth.async_session_maker", return_value=session_cm
        ):
            await mw.dispatch(request, _ok_call_next)

        assert getattr(request.state, "proxy_user", None) is None

    # ── SPEC 7: proxy_user set ─────────────────────────────────────────────────

    async def test_valid_email_sets_proxy_user_to_resolved_user(self):
        """
        GIVEN  valid email header and active user in DB
        WHEN   middleware runs
        THEN   request.state.proxy_user is the resolved user object
        """
        mw = _make_middleware()
        user = _make_user(email=_EMAIL, last_login=datetime.now(UTC))
        request = _make_request(headers={"x-auth-request-email": _EMAIL})

        session = AsyncMock()
        found_result = MagicMock()
        found_result.unique.return_value.scalar_one_or_none.return_value = user
        # last_login is recent → needs_update=False → only one execute call
        session.execute = AsyncMock(return_value=found_result)
        session_cm = _make_session_cm(session)

        with patch(
            "app.middleware.proxy_auth.async_session_maker", return_value=session_cm
        ):
            await mw.dispatch(request, _ok_call_next)

        assert request.state.proxy_user is user

    # ── SPEC 8: email normalisation ────────────────────────────────────────────

    async def test_email_with_uppercase_and_whitespace_is_normalised(self):
        """
        GIVEN  email header value "  ALICE@EXAMPLE.COM  "
        WHEN   request arrives
        THEN   _normalise_email is called with the raw value and the lookup uses
               the normalised form
        """
        mw = _make_middleware()
        raw_email = "  ALICE@EXAMPLE.COM  "
        normalised = "alice@example.com"
        user = _make_user(email=normalised, last_login=datetime.now(UTC))
        request = _make_request(headers={"x-auth-request-email": raw_email})

        session = AsyncMock()
        found_result = MagicMock()
        found_result.unique.return_value.scalar_one_or_none.return_value = user
        session.execute = AsyncMock(return_value=found_result)
        session_cm = _make_session_cm(session)

        with (
            patch(
                "app.middleware.proxy_auth.async_session_maker", return_value=session_cm
            ),
            patch(
                "app.middleware.proxy_auth._normalise_email",
                wraps=_normalise_email,
            ) as mock_norm,
        ):
            await mw.dispatch(request, _ok_call_next)

        mock_norm.assert_called_once_with(raw_email.strip())
        assert request.state.proxy_user is user

    # ── SPEC 9: race condition / IntegrityError ──────────────────────────────

    async def test_race_condition_fallback_select_sets_proxy_user(self):
        """
        GIVEN  two concurrent requests for the same new email
        WHEN   INSERT raises IntegrityError (the other request won the race)
        THEN   fallback SELECT finds the user committed by the winner, proxy_user set
        """
        mw = _make_middleware()
        # race_user was committed by the concurrent winner; it has a recent last_login
        # so the throttle check (needs_update) is False, avoiding a third execute call.
        race_user = _make_user(email=_EMAIL, last_login=datetime.now(UTC))
        request = _make_request(headers={"x-auth-request-email": _EMAIL})

        session = AsyncMock()
        session.add = MagicMock()  # add() is sync; avoid AsyncMock warning
        # Call 1: initial SELECT — no user found
        no_user_result = MagicMock()
        no_user_result.unique.return_value.scalar_one_or_none.return_value = None
        # Call 2: fallback SELECT after rollback — race_user found
        fallback_result = MagicMock()
        fallback_result.unique.return_value.scalar_one_or_none.return_value = race_user
        session.execute = AsyncMock(side_effect=[no_user_result, fallback_result])
        # INSERT commit raises IntegrityError; any subsequent commits should succeed
        session.commit = AsyncMock(side_effect=[IntegrityError(None, None, None), None])
        session_cm = _make_session_cm(session)

        with patch(
            "app.middleware.proxy_auth.async_session_maker", return_value=session_cm
        ):
            await mw.dispatch(request, _ok_call_next)

        session.rollback.assert_called_once()
        assert request.state.proxy_user is race_user

    # ── SPEC 10: bare username → email synthesis ──────────────────────────────

    async def test_bare_username_synthesizes_email_via_default_email_domain(self):
        """
        GIVEN  X-Auth-Request-Email contains a bare username (no @)
               AND config.DEFAULT_EMAIL_DOMAIN is set
        WHEN   request arrives
        THEN   middleware synthesizes {username}@{DEFAULT_EMAIL_DOMAIN}
               AND passes it to _resolve_user
        """
        mw = _make_middleware()
        resolved = _make_user(email="testuser@askii.ai")
        mw._resolve_user = AsyncMock(return_value=resolved)
        request = _make_request(headers={"x-auth-request-email": "testuser"})

        with patch("app.middleware.proxy_auth.config") as mock_cfg:
            mock_cfg.DEFAULT_EMAIL_DOMAIN = "askii.ai"
            await mw.dispatch(request, _ok_call_next)

        mw._resolve_user.assert_called_once()
        called_email = mw._resolve_user.call_args.args[0]
        assert called_email == "testuser@askii.ai"
        assert request.state.proxy_user is resolved
