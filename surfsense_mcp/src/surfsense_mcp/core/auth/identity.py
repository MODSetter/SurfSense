"""Request-scoped caller identity.

Over streamable-http one process serves many users, so the caller's key lives
in a contextvar for the life of a single request: the auth middleware binds it,
and the client reads it when building the outbound backend call. Under stdio
there is no request, the contextvar stays empty, and the env key is used.

The contextvar is request-scoped, not stored state — it is re-derived from the
header on every request, which is what keeps the server stateless.
"""

from __future__ import annotations

from contextvars import ContextVar, Token

_LOCAL_IDENTITY = "__local__"

_api_key: ContextVar[str | None] = ContextVar("surfsense_api_key", default=None)


def bind_api_key(api_key: str | None) -> Token:
    """Bind the caller's key to the current request; returns a reset token."""
    return _api_key.set(api_key)


def unbind_api_key(token: Token) -> None:
    """Release the binding once the request is done."""
    _api_key.reset(token)


def current_api_key() -> str | None:
    """The caller's key for the in-flight request, or ``None`` under stdio."""
    return _api_key.get()


def current_identity() -> str:
    """Stable per-caller key for scoping request state.

    The token identifies the account, so state keyed on it is naturally
    per-user and survives reconnects. Under stdio all calls share one identity.
    """
    return _api_key.get() or _LOCAL_IDENTITY
