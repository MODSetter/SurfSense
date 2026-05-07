"""Shared strict MCP OAuth fake dispatcher for E2E tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import patch


@dataclass(frozen=True)
class _OAuthHandler:
    mcp_url: str
    discovery_metadata: dict[str, Any]
    client_id: str
    client_secret: str
    token_endpoint: str
    registration_endpoint: str
    oauth_code: str
    access_token: str
    refresh_token: str
    scope: str
    redirect_uri_substring: str
    expected_origin_override: str | None = None


_SERVICES_BY_MCP_URL: dict[str, _OAuthHandler] = {}
_SERVICES_BY_REGISTRATION_URL: dict[str, _OAuthHandler] = {}
_SERVICES_BY_TOKEN_URL: dict[str, _OAuthHandler] = {}


def register_service(
    *,
    mcp_url: str,
    discovery_metadata: dict[str, Any],
    client_id: str,
    client_secret: str,
    token_endpoint: str,
    registration_endpoint: str,
    oauth_code: str,
    access_token: str,
    refresh_token: str,
    scope: str,
    redirect_uri_substring: str,
    expected_origin_override: str | None = None,
) -> None:
    """Register deterministic MCP OAuth behavior for one service."""
    handler = _OAuthHandler(
        mcp_url=mcp_url,
        discovery_metadata=discovery_metadata,
        client_id=client_id,
        client_secret=client_secret,
        token_endpoint=token_endpoint,
        registration_endpoint=registration_endpoint,
        oauth_code=oauth_code,
        access_token=access_token,
        refresh_token=refresh_token,
        scope=scope,
        redirect_uri_substring=redirect_uri_substring,
        expected_origin_override=expected_origin_override,
    )
    _register_unique(_SERVICES_BY_MCP_URL, mcp_url, handler, "MCP URL")
    _register_unique(
        _SERVICES_BY_REGISTRATION_URL,
        registration_endpoint,
        handler,
        "registration endpoint",
    )
    _register_unique(_SERVICES_BY_TOKEN_URL, token_endpoint, handler, "token endpoint")


def _register_unique(
    registry: dict[str, _OAuthHandler],
    key: str,
    handler: _OAuthHandler,
    label: str,
) -> None:
    existing = registry.get(key)
    if existing is not None and existing != handler:
        raise ValueError(f"MCP OAuth fake {label} already registered: {key!r}.")
    registry[key] = handler


async def _fake_discover_oauth_metadata(
    mcp_url: str,
    *,
    origin_override: str | None = None,
    timeout: float = 15.0,
) -> dict[str, Any]:
    del timeout
    handler = _SERVICES_BY_MCP_URL.get(mcp_url)
    if handler is None:
        raise NotImplementedError(f"Unexpected MCP OAuth discovery url={mcp_url!r}")
    if origin_override != handler.expected_origin_override:
        raise ValueError(
            f"Unexpected MCP OAuth origin_override for {mcp_url!r}: "
            f"{origin_override!r}"
        )
    return dict(handler.discovery_metadata)


async def _fake_register_client(
    registration_endpoint: str,
    redirect_uri: str,
    *,
    client_name: str = "SurfSense",
    timeout: float = 15.0,
) -> dict[str, Any]:
    del timeout
    handler = _SERVICES_BY_REGISTRATION_URL.get(registration_endpoint)
    if handler is None:
        raise NotImplementedError(
            f"Unexpected MCP OAuth DCR endpoint={registration_endpoint!r}"
        )
    if client_name != "SurfSense":
        raise ValueError(f"Unexpected MCP OAuth DCR client_name={client_name!r}")
    if handler.redirect_uri_substring not in redirect_uri:
        raise ValueError(
            f"Unexpected MCP OAuth DCR redirect_uri={redirect_uri!r}; "
            f"expected {handler.redirect_uri_substring!r}"
        )
    return {
        "client_id": handler.client_id,
        "client_secret": handler.client_secret,
        "client_id_issued_at": 1_776_621_600,
        "token_endpoint_auth_method": "client_secret_basic",
    }


async def _fake_exchange_code_for_tokens(
    token_endpoint: str,
    code: str,
    redirect_uri: str,
    client_id: str,
    client_secret: str,
    code_verifier: str,
    *,
    timeout: float = 30.0,
) -> dict[str, Any]:
    del timeout
    handler = _SERVICES_BY_TOKEN_URL.get(token_endpoint)
    if handler is None:
        raise NotImplementedError(
            f"Unexpected MCP OAuth token_endpoint={token_endpoint!r}"
        )
    if code != handler.oauth_code:
        raise ValueError(f"Unexpected fake MCP OAuth code: {code!r}")
    if handler.redirect_uri_substring not in redirect_uri:
        raise ValueError(
            f"Unexpected MCP OAuth token redirect_uri={redirect_uri!r}; "
            f"expected {handler.redirect_uri_substring!r}"
        )
    if client_id != handler.client_id or client_secret != handler.client_secret:
        raise ValueError(
            "Unexpected MCP OAuth client credentials: "
            f"client_id={client_id!r} client_secret={client_secret!r}"
        )
    if not code_verifier:
        raise ValueError("MCP OAuth token exchange missing code_verifier.")
    return {
        "access_token": handler.access_token,
        "refresh_token": handler.refresh_token,
        "expires_in": 3600,
        "scope": handler.scope,
        "token_type": "Bearer",
    }


async def _fake_refresh_access_token(
    token_endpoint: str,
    refresh_token: str,
    client_id: str,
    client_secret: str,
    *,
    timeout: float = 30.0,
) -> dict[str, Any]:
    del timeout
    handler = _SERVICES_BY_TOKEN_URL.get(token_endpoint)
    if handler is None:
        raise NotImplementedError(
            f"Unexpected MCP OAuth refresh token_endpoint={token_endpoint!r}"
        )
    if refresh_token != handler.refresh_token:
        raise ValueError(f"Unexpected fake MCP OAuth refresh token: {refresh_token!r}")
    if client_id != handler.client_id or client_secret != handler.client_secret:
        raise ValueError(
            "Unexpected MCP OAuth refresh client credentials: "
            f"client_id={client_id!r} client_secret={client_secret!r}"
        )
    return {
        "access_token": handler.access_token,
        "refresh_token": handler.refresh_token,
        "expires_in": 3600,
        "scope": handler.scope,
        "token_type": "Bearer",
    }


def install(active_patches: list[Any]) -> None:
    """Patch generic MCP OAuth helper boundaries exactly once."""
    targets = [
        (
            "app.services.mcp_oauth.discovery.discover_oauth_metadata",
            _fake_discover_oauth_metadata,
        ),
        ("app.services.mcp_oauth.discovery.register_client", _fake_register_client),
        (
            "app.services.mcp_oauth.discovery.exchange_code_for_tokens",
            _fake_exchange_code_for_tokens,
        ),
        (
            "app.services.mcp_oauth.discovery.refresh_access_token",
            _fake_refresh_access_token,
        ),
    ]
    for target, replacement in targets:
        p = patch(target, replacement)
        p.start()
        active_patches.append(p)
