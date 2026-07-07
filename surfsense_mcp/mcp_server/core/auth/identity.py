"""Request-scoped caller identity.

Over streamable-http one process serves many users, so the caller's key lives in
a contextvar for the life of a request: the auth middleware binds it and the
client reads it when calling the backend. Under stdio there is no request, so the
contextvar is empty and the env key is used instead.
"""

from __future__ import annotations

from contextvars import ContextVar, Token

_LOCAL_IDENTITY = "__local__"

_api_key: ContextVar[str | None] = ContextVar("surfsense_api_key", default=None)


def bind_api_key(api_key: str | None) -> Token:
    """Bind the caller's key to the current request; returns a reset token."""
    return _api_key.set(api_key)


def unbind_api_key(token: Token) -> None:
    _api_key.reset(token)


def current_api_key() -> str | None:
    """The caller's key for the in-flight request, or ``None`` under stdio."""
    return _api_key.get()


def current_identity() -> str:
    """Stable per-caller key for scoping request state; shared under stdio."""
    return _api_key.get() or _LOCAL_IDENTITY
