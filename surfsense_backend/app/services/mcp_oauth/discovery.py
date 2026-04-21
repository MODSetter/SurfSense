"""MCP OAuth 2.1 metadata discovery, Dynamic Client Registration, and token exchange."""

from __future__ import annotations

import base64
import logging
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


async def discover_oauth_metadata(mcp_url: str, *, timeout: float = 15.0) -> dict:
    """Fetch OAuth 2.1 metadata from the MCP server's well-known endpoint.

    Per the MCP spec the discovery document lives at the *origin* of the
    MCP server URL, not at the MCP endpoint path.
    """
    parsed = urlparse(mcp_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    discovery_url = f"{origin}/.well-known/oauth-authorization-server"

    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.get(discovery_url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()


async def register_client(
    registration_endpoint: str,
    redirect_uri: str,
    *,
    client_name: str = "SurfSense",
    timeout: float = 15.0,
) -> dict:
    """Perform Dynamic Client Registration (RFC 7591)."""
    payload = {
        "client_name": client_name,
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "client_secret_basic",
    }

    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.post(
            registration_endpoint, json=payload, timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()


async def exchange_code_for_tokens(
    token_endpoint: str,
    code: str,
    redirect_uri: str,
    client_id: str,
    client_secret: str,
    code_verifier: str,
    *,
    timeout: float = 30.0,
) -> dict:
    """Exchange an authorization code for access + refresh tokens."""
    creds = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.post(
            token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {creds}",
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()


async def refresh_access_token(
    token_endpoint: str,
    refresh_token: str,
    client_id: str,
    client_secret: str,
    *,
    timeout: float = 30.0,
) -> dict:
    """Refresh an expired access token."""
    creds = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.post(
            token_endpoint,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {creds}",
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()
