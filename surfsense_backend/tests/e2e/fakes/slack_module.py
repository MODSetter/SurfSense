"""Strict Slack MCP OAuth/tool fakes for Playwright E2E."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from tests.e2e.fakes import mcp_oauth_runtime, mcp_runtime

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "slack_messages.json"

_AUTHORIZATION_URL = "https://slack.com/oauth/v2_user/authorize"
_REGISTRATION_URL = "https://e2e-fake.invalid/mcp/slack-unused-register"
_TOKEN_URL = "https://slack.com/api/oauth.v2.user.access"
_MCP_URL = "https://mcp.slack.com/mcp"

_CLIENT_ID = "fake-slack-mcp-client-id"
_CLIENT_SECRET = "fake-slack-mcp-client-secret"
_ACCESS_TOKEN = "fake-slack-mcp-access-token"
_REFRESH_TOKEN = "fake-slack-mcp-refresh-token"
_OAUTH_CODE = "fake-slack-oauth-code"
_SCOPE = (
    "search:read.public search:read.private search:read.mpim search:read.im "
    "channels:history groups:history mpim:history im:history"
)


def _load_fixture() -> dict[str, Any]:
    with _FIXTURE_PATH.open() as f:
        return json.load(f)


_FIXTURE = _load_fixture()


async def _list_tools() -> SimpleNamespace:
    return SimpleNamespace(
        tools=[
            SimpleNamespace(
                name="slack_search_channels",
                description="Search Slack channels visible to the authenticated user.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Text to search for in Slack channel names.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of channels to return.",
                        },
                    },
                    "required": [],
                },
            ),
            SimpleNamespace(
                name="slack_read_channel",
                description="Read messages from a Slack channel.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "channel_id": {
                            "type": "string",
                            "description": "Slack channel id.",
                        }
                    },
                    "required": ["channel_id"],
                },
            ),
            SimpleNamespace(
                name="slack_read_thread",
                description="Read a Slack thread from a channel.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "channel_id": {
                            "type": "string",
                            "description": "Slack channel id.",
                        },
                        "thread_ts": {
                            "type": "string",
                            "description": "Slack thread timestamp.",
                        },
                    },
                    "required": ["channel_id", "thread_ts"],
                },
            ),
        ]
    )


async def _call_tool(
    tool_name: str, arguments: dict[str, Any] | None = None
) -> SimpleNamespace:
    arguments = arguments or {}
    channel = _FIXTURE["channel"]
    message = _FIXTURE["messages"][0]

    if tool_name == "slack_search_channels":
        query = str(arguments.get("query", ""))
        if query and channel["name"].lower() not in query.lower():
            raise ValueError(f"Unexpected Slack channel query: {query!r}")
        text = (
            f"#{channel['name']} ({channel['id']})\n"
            f"purpose: {channel['purpose']}\n"
            f"latest_message: {message['text']}"
        )
        return SimpleNamespace(content=[SimpleNamespace(text=text)])

    if tool_name in {"slack_read_channel", "slack_read_thread"}:
        raise NotImplementedError(
            f"Slack E2E fake does not exercise {tool_name!r}; "
            "extend slack_module.py before using it in a journey."
        )

    raise NotImplementedError(f"Unexpected Slack MCP tool call: {tool_name!r}")


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
    if token_endpoint != _TOKEN_URL:
        return await mcp_oauth_runtime._fake_exchange_code_for_tokens(
            token_endpoint,
            code,
            redirect_uri,
            client_id,
            client_secret,
            code_verifier,
            timeout=timeout,
        )
    del timeout

    if code != _OAUTH_CODE:
        raise ValueError(f"Unexpected fake Slack OAuth code: {code!r}")
    if "/api/v1/auth/mcp/slack/connector/callback" not in redirect_uri:
        raise ValueError(f"Unexpected Slack redirect_uri={redirect_uri!r}")
    if client_id != _CLIENT_ID or client_secret != _CLIENT_SECRET:
        raise ValueError(
            "Unexpected Slack client credentials: "
            f"client_id={client_id!r} client_secret={client_secret!r}"
        )
    if not code_verifier:
        raise ValueError("Slack token exchange missing code_verifier.")

    team = _FIXTURE["team"]
    return {
        "ok": True,
        "scope": _SCOPE,
        "token_type": "Bearer",
        "expires_in": 3600,
        "refresh_token": _REFRESH_TOKEN,
        "authed_user": {
            "id": "U_FAKE_SLACK_USER",
            "scope": _SCOPE,
            "access_token": _ACCESS_TOKEN,
            "refresh_token": _REFRESH_TOKEN,
            "expires_in": 3600,
            "token_type": "Bearer",
        },
        "team": {
            "id": team["id"],
            "name": team["name"],
        },
    }


def install(active_patches: list[Any]) -> None:
    """Register Slack MCP OAuth/tool handlers with the shared dispatchers."""
    mcp_oauth_runtime.register_service(
        mcp_url=_MCP_URL,
        discovery_metadata={
            "issuer": "https://slack.com",
            "authorization_endpoint": _AUTHORIZATION_URL,
            "token_endpoint": _TOKEN_URL,
            "registration_endpoint": _REGISTRATION_URL,
            "code_challenge_methods_supported": ["S256"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "response_types_supported": ["code"],
        },
        client_id=_CLIENT_ID,
        client_secret=_CLIENT_SECRET,
        token_endpoint=_TOKEN_URL,
        registration_endpoint=_REGISTRATION_URL,
        oauth_code=_OAUTH_CODE,
        access_token=_ACCESS_TOKEN,
        refresh_token=_REFRESH_TOKEN,
        scope=_SCOPE,
        redirect_uri_substring="/api/v1/auth/mcp/slack/connector/callback",
    )
    mcp_runtime.register(
        url=_MCP_URL,
        expected_bearer=_ACCESS_TOKEN,
        list_tools=_list_tools,
        call_tool=_call_tool,
    )
    p = patch(
        "app.services.mcp_oauth.discovery.exchange_code_for_tokens",
        _fake_exchange_code_for_tokens,
    )
    p.start()
    active_patches.append(p)
