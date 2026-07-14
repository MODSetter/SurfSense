"""Dual-mode credential resolver + httpx client factory with 401 auto-refresh.

SurfSense supports ``AUTH_TYPE=LOCAL`` (email + password) and
``AUTH_TYPE=GOOGLE`` (Google OAuth → frontend stores JWT in ``localStorage``).
There is no headless equivalent of the Google flow, so the harness handles
both modes by treating the JWT as the universal credential:

* **LOCAL**: harness POSTs JSON ``email`` + ``password`` to
  ``/auth/desktop/login``, reads ``{access_token, refresh_token}``.
* **GOOGLE / pre-issued JWT**: operator pastes their existing JWT (and
  optionally refresh token) into ``SURFSENSE_JWT`` /
  ``SURFSENSE_REFRESH_TOKEN``; harness skips login.

Either way ``client_with_auth`` returns one shared
``httpx.AsyncClient`` with ``Authorization: Bearer <jwt>`` set and an
event hook that, on a 401 with a refresh token in scope, calls
``POST /auth/jwt/refresh`` and retries the original request once. JWT
lifetime defaults to one day backend-side, so this matters for long
MIRAGE runs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from .config import Config

logger = logging.getLogger(__name__)


class CredentialError(RuntimeError):
    """Raised when no credential mode is configured."""


_NO_CREDENTIALS_MESSAGE = (
    "No SurfSense credentials configured. Set ONE of:\n"
    "  (LOCAL)  SURFSENSE_USER_EMAIL + SURFSENSE_USER_PASSWORD\n"
    "  (GOOGLE) SURFSENSE_JWT (and optionally SURFSENSE_REFRESH_TOKEN)\n"
    "For GOOGLE: use a PAT or operator-issued bearer token and set "
    "SURFSENSE_JWT (plus SURFSENSE_REFRESH_TOKEN if available)."
)


@dataclass
class TokenBundle:
    """Mutable token state — refresh hook updates ``access_token`` in place."""

    access_token: str
    refresh_token: str | None = None
    # ``mode`` is informational only ("local" or "jwt"); used in error messages.
    mode: str = "jwt"


# ---------------------------------------------------------------------------
# Token acquisition
# ---------------------------------------------------------------------------


async def acquire_token(config: Config, *, http: httpx.AsyncClient | None = None) -> TokenBundle:
    """Resolve credentials → ``TokenBundle``.

    Precedence:

    1. ``SURFSENSE_JWT`` set → use it directly. Refresh token captured if
       supplied.
    2. ``SURFSENSE_USER_EMAIL`` + ``SURFSENSE_USER_PASSWORD`` set →
       JSON POST to ``/auth/desktop/login``.
    3. Neither → raise ``CredentialError``.

    The optional ``http`` argument lets tests inject a mocked client; if
    omitted a one-shot client is created for the login call only.
    """

    if config.has_jwt_mode():
        return TokenBundle(
            access_token=config.surfsense_jwt or "",
            refresh_token=config.surfsense_refresh_token,
            mode="jwt",
        )

    if config.has_local_mode():

        async def _login(client: httpx.AsyncClient) -> TokenBundle:
            response = await client.post(
                f"{config.surfsense_api_base}/auth/desktop/login",
                json={
                    "email": config.surfsense_user_email,
                    "password": config.surfsense_user_password,
                },
                headers={"Accept": "application/json"},
            )
            if response.status_code != 200:
                raise CredentialError(
                    f"LOCAL login failed (HTTP {response.status_code}): {_safe_text(response)}"
                )
            payload = response.json()
            access = payload.get("access_token")
            if not access:
                raise CredentialError(f"LOCAL login response missing access_token: {payload!r}")
            return TokenBundle(
                access_token=access,
                refresh_token=payload.get("refresh_token") or None,
                mode="local",
            )

        if http is not None:
            return await _login(http)
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            return await _login(client)

    raise CredentialError(_NO_CREDENTIALS_MESSAGE)


def _safe_text(response: httpx.Response, *, limit: int = 200) -> str:
    body = response.text or ""
    if len(body) > limit:
        return body[:limit] + "…"
    return body


# ---------------------------------------------------------------------------
# httpx client + 401 auto-refresh
# ---------------------------------------------------------------------------


class _AuthState:
    """Shared mutable holder closed over by the auth event hook.

    Kept private so callers can't accidentally mutate the access token
    out-of-band; ``client_with_auth`` returns the client directly.
    """

    def __init__(self, config: Config, tokens: TokenBundle) -> None:
        self.config = config
        self.tokens = tokens
        self._refresh_in_flight: bool = False


def _build_auth_request(state: _AuthState, request: httpx.Request) -> None:
    """Stamp the current bearer onto ``request`` (request-event hook)."""

    request.headers["Authorization"] = f"Bearer {state.tokens.access_token}"


async def _refresh_access_token(
    state: _AuthState, transport: httpx.AsyncBaseTransport | None = None
) -> bool:
    """POST ``/auth/jwt/refresh`` with the current refresh token.

    Returns ``True`` on success and updates ``state.tokens`` in place.
    Returns ``False`` if no refresh token is configured or the call fails.
    Recursive 401s are avoided by using a *new* client without the auth
    hook.
    """

    refresh = state.tokens.refresh_token
    if not refresh:
        return False
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0),
            transport=transport,
        ) as inner:
            response = await inner.post(
                f"{state.config.surfsense_api_base}/auth/jwt/refresh",
                json={"refresh_token": refresh},
                headers={"Accept": "application/json"},
            )
    except httpx.HTTPError as exc:
        logger.warning("Token refresh transport error: %s", exc)
        return False
    if response.status_code != 200:
        logger.warning(
            "Token refresh rejected (HTTP %s): %s",
            response.status_code,
            _safe_text(response),
        )
        return False
    payload = response.json()
    new_access = payload.get("access_token")
    if not new_access:
        logger.warning("Refresh response missing access_token: %r", payload)
        return False
    state.tokens.access_token = new_access
    new_refresh = payload.get("refresh_token")
    if new_refresh:
        state.tokens.refresh_token = new_refresh
    return True


def client_with_auth(
    config: Config,
    tokens: TokenBundle,
    *,
    timeout: float = 60.0,
    transport: httpx.AsyncBaseTransport | None = None,
    base_url: str | None = None,
) -> httpx.AsyncClient:
    """Build a single shared ``httpx.AsyncClient`` for the SurfSense API.

    * Stamps ``Authorization: Bearer <jwt>`` on every outgoing request.
    * On any 401 response, attempts a single refresh (if a refresh token
      is configured) and retries the original request once. The retry
      uses a fresh stamping of the bearer header, so a successful
      refresh transparently unblocks long runs.
    * The retry is best-effort — repeated 401s after a refresh attempt
      are surfaced to the caller so they can re-auth manually.

    Pass ``base_url`` to scope a sub-client (e.g. tests). The default
    keeps full URLs in calling code, which makes route-spec citations in
    the codebase easier to grep.
    """

    state = _AuthState(config, tokens)

    async def _request_hook(request: httpx.Request) -> None:
        _build_auth_request(state, request)

    # ``send`` is overridden in ``_AuthAwareClient`` to retry once on 401
    # after refreshing the bearer. httpx's response event-hook can't
    # *replace* a response, so we need a subclass to do the replay.
    client = _AuthAwareClient(
        state=state,
        transport=transport,
        timeout=httpx.Timeout(timeout, connect=10.0),
        base_url=base_url or "",
        event_hooks={"request": [_request_hook]},
    )
    return client


class _AuthAwareClient(httpx.AsyncClient):
    """``AsyncClient`` that retries once on 401 after refreshing the token."""

    def __init__(self, *, state: _AuthState, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._auth_state = state

    async def send(  # type: ignore[override]
        self, request: httpx.Request, **kwargs: Any
    ) -> httpx.Response:
        response = await super().send(request, **kwargs)
        if response.status_code != 401:
            return response
        # Don't refresh while a refresh is itself in flight.
        if self._auth_state._refresh_in_flight:
            return response
        self._auth_state._refresh_in_flight = True
        try:
            refreshed = await _refresh_access_token(self._auth_state)
        finally:
            self._auth_state._refresh_in_flight = False
        if not refreshed:
            return response
        # Re-stamp and replay once. ``request`` is reusable.
        await response.aclose()
        request.headers["Authorization"] = f"Bearer {self._auth_state.tokens.access_token}"
        return await super().send(request, **kwargs)


__all__ = [
    "CredentialError",
    "TokenBundle",
    "acquire_token",
    "client_with_auth",
]
