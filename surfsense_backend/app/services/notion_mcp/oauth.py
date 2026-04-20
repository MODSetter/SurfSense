"""OAuth 2.0 + PKCE utilities for Notion's remote MCP server.

Implements the flow described in the official guide:
https://developers.notion.com/guides/mcp/build-mcp-client

Steps:
  1. Discover OAuth metadata (RFC 9470 → RFC 8414)
  2. Dynamic client registration (RFC 7591)
  3. Build authorization URL with PKCE code_challenge
  4. Exchange authorization code + code_verifier for tokens
  5. Refresh access tokens (with refresh-token rotation)

All functions are stateless — callers (route handlers) manage storage.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

logger = logging.getLogger(__name__)

NOTION_MCP_SERVER_URL = "https://mcp.notion.com/mcp"
_HTTP_TIMEOUT = 30.0


@dataclass(frozen=True)
class OAuthMetadata:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    registration_endpoint: str | None
    code_challenge_methods_supported: list[str]


@dataclass(frozen=True)
class ClientCredentials:
    client_id: str
    client_secret: str | None = None
    client_id_issued_at: int | None = None
    client_secret_expires_at: int | None = None


@dataclass(frozen=True)
class TokenSet:
    access_token: str
    refresh_token: str | None
    token_type: str
    expires_in: int | None
    expires_at: datetime | None
    scope: str | None


# ---------------------------------------------------------------------------
# Step 1 — OAuth discovery
# ---------------------------------------------------------------------------


async def discover_oauth_metadata(
    mcp_server_url: str = NOTION_MCP_SERVER_URL,
) -> OAuthMetadata:
    """Discover OAuth endpoints via RFC 9470 + RFC 8414.

    1. Fetch protected-resource metadata to find the authorization server.
    2. Fetch authorization-server metadata to get OAuth endpoints.
    """
    from urllib.parse import urlparse

    parsed = urlparse(mcp_server_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path.rstrip("/")

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        # RFC 9470 — Protected Resource Metadata
        # URL format: {origin}/.well-known/oauth-protected-resource{path}
        pr_url = f"{origin}/.well-known/oauth-protected-resource{path}"
        pr_resp = await client.get(pr_url)
        pr_resp.raise_for_status()
        pr_data = pr_resp.json()

        auth_servers = pr_data.get("authorization_servers", [])
        if not auth_servers:
            raise ValueError("No authorization_servers in protected resource metadata")
        auth_server_url = auth_servers[0]

        # RFC 8414 — Authorization Server Metadata
        as_url = f"{auth_server_url}/.well-known/oauth-authorization-server"
        as_resp = await client.get(as_url)
        as_resp.raise_for_status()
        as_data = as_resp.json()

    if not as_data.get("authorization_endpoint") or not as_data.get("token_endpoint"):
        raise ValueError("Missing required OAuth endpoints in server metadata")

    return OAuthMetadata(
        issuer=as_data.get("issuer", auth_server_url),
        authorization_endpoint=as_data["authorization_endpoint"],
        token_endpoint=as_data["token_endpoint"],
        registration_endpoint=as_data.get("registration_endpoint"),
        code_challenge_methods_supported=as_data.get(
            "code_challenge_methods_supported", []
        ),
    )


# ---------------------------------------------------------------------------
# Step 2 — Dynamic client registration (RFC 7591)
# ---------------------------------------------------------------------------


async def register_client(
    metadata: OAuthMetadata,
    redirect_uri: str,
    client_name: str = "SurfSense",
) -> ClientCredentials:
    """Dynamically register an OAuth client with the Notion MCP server."""
    if not metadata.registration_endpoint:
        raise ValueError("Server does not support dynamic client registration")

    payload = {
        "client_name": client_name,
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.post(
            metadata.registration_endpoint,
            json=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        if not resp.is_success:
            logger.error(
                "Dynamic client registration failed (%s): %s",
                resp.status_code,
                resp.text,
            )
            resp.raise_for_status()
        data = resp.json()

    return ClientCredentials(
        client_id=data["client_id"],
        client_secret=data.get("client_secret"),
        client_id_issued_at=data.get("client_id_issued_at"),
        client_secret_expires_at=data.get("client_secret_expires_at"),
    )


# ---------------------------------------------------------------------------
# Step 3 — Build authorization URL
# ---------------------------------------------------------------------------


def build_authorization_url(
    metadata: OAuthMetadata,
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    state: str,
) -> str:
    """Build the OAuth authorization URL with PKCE parameters."""
    from urllib.parse import urlencode

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
        "prompt": "consent",
    }
    return f"{metadata.authorization_endpoint}?{urlencode(params)}"


# ---------------------------------------------------------------------------
# Step 4 — Exchange authorization code for tokens
# ---------------------------------------------------------------------------


async def exchange_code_for_tokens(
    code: str,
    code_verifier: str,
    metadata: OAuthMetadata,
    client_id: str,
    redirect_uri: str,
    client_secret: str | None = None,
) -> TokenSet:
    """Exchange an authorization code + PKCE verifier for tokens."""
    form_data: dict[str, Any] = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }
    if client_secret:
        form_data["client_secret"] = client_secret

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.post(
            metadata.token_endpoint,
            data=form_data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )
        if not resp.is_success:
            body = resp.text
            raise ValueError(f"Token exchange failed ({resp.status_code}): {body}")
        tokens = resp.json()

    if not tokens.get("access_token"):
        raise ValueError("No access_token in token response")

    expires_at = None
    if tokens.get("expires_in"):
        expires_at = datetime.now(UTC) + timedelta(seconds=int(tokens["expires_in"]))

    return TokenSet(
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
        token_type=tokens.get("token_type", "Bearer"),
        expires_in=tokens.get("expires_in"),
        expires_at=expires_at,
        scope=tokens.get("scope"),
    )


# ---------------------------------------------------------------------------
# Step 5 — Refresh access token
# ---------------------------------------------------------------------------


async def refresh_access_token(
    refresh_token: str,
    metadata: OAuthMetadata,
    client_id: str,
    client_secret: str | None = None,
) -> TokenSet:
    """Refresh an access token.

    Notion MCP uses refresh-token rotation: each refresh returns a new
    refresh_token and invalidates the old one.  Callers MUST persist the
    new refresh_token atomically with the new access_token.
    """
    form_data: dict[str, Any] = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }
    if client_secret:
        form_data["client_secret"] = client_secret

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.post(
            metadata.token_endpoint,
            data=form_data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )

        if not resp.is_success:
            body = resp.text
            try:
                error_data = resp.json()
                error_code = error_data.get("error", "")
                if error_code == "invalid_grant":
                    raise ValueError("REAUTH_REQUIRED")
            except ValueError:
                if "REAUTH_REQUIRED" in str(resp.text) or resp.status_code == 401:
                    raise
            raise ValueError(f"Token refresh failed ({resp.status_code}): {body}")

        tokens = resp.json()

    if not tokens.get("access_token"):
        raise ValueError("No access_token in refresh response")

    expires_at = None
    if tokens.get("expires_in"):
        expires_at = datetime.now(UTC) + timedelta(seconds=int(tokens["expires_in"]))

    return TokenSet(
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
        token_type=tokens.get("token_type", "Bearer"),
        expires_in=tokens.get("expires_in"),
        expires_at=expires_at,
        scope=tokens.get("scope"),
    )
