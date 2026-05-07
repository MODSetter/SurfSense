"""Strict Linear MCP OAuth/tool fakes for Playwright E2E."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from tests.e2e.fakes import mcp_oauth_runtime, mcp_runtime

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "linear_issues.json"

_DISCOVERY_URL = "https://mcp.linear.app/.well-known/oauth-authorization-server"
_AUTHORIZATION_URL = "https://mcp.linear.app/authorize"
_REGISTRATION_URL = "https://mcp.linear.app/register"
_TOKEN_URL = "https://mcp.linear.app/token"
_MCP_URL = "https://mcp.linear.app/mcp"

_CLIENT_ID = "fake-linear-mcp-client-id"
_CLIENT_SECRET = "fake-linear-mcp-client-secret"
_ACCESS_TOKEN = "fake-linear-mcp-access-token"
_REFRESH_TOKEN = "fake-linear-mcp-refresh-token"
_OAUTH_CODE = "fake-linear-oauth-code"


def _load_fixture() -> dict[str, Any]:
    with _FIXTURE_PATH.open() as f:
        return json.load(f)


_FIXTURE = _load_fixture()


class _StrictFakeMixin:
    _component_name: str = "<unknown>"

    def __getattr__(self, name: str) -> Any:
        raise NotImplementedError(
            f"E2E Linear fake missing surface: {self._component_name}.{name!r}. "
            "Add it to surfsense_backend/tests/e2e/fakes/linear_module.py."
        )


async def _fake_discover_oauth_metadata(
    mcp_url: str,
    *,
    origin_override: str | None = None,
    timeout: float = 15.0,
) -> dict[str, Any]:
    del origin_override, timeout
    if mcp_url != _MCP_URL:
        raise NotImplementedError(f"Unexpected Linear MCP discovery url={mcp_url!r}")
    return {
        "issuer": "https://mcp.linear.app",
        "authorization_endpoint": _AUTHORIZATION_URL,
        "token_endpoint": _TOKEN_URL,
        "registration_endpoint": _REGISTRATION_URL,
        "code_challenge_methods_supported": ["S256"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "response_types_supported": ["code"],
    }


async def _fake_register_client(
    registration_endpoint: str,
    redirect_uri: str,
    *,
    client_name: str = "SurfSense",
    timeout: float = 15.0,
) -> dict[str, Any]:
    del timeout
    if registration_endpoint != _REGISTRATION_URL:
        raise NotImplementedError(
            f"Unexpected Linear DCR endpoint={registration_endpoint!r}"
        )
    if client_name != "SurfSense":
        raise ValueError(f"Unexpected Linear DCR client_name={client_name!r}")
    if "/api/v1/auth/mcp/linear/connector/callback" not in redirect_uri:
        raise ValueError(f"Unexpected Linear redirect_uri={redirect_uri!r}")
    return {
        "client_id": _CLIENT_ID,
        "client_secret": _CLIENT_SECRET,
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
    if token_endpoint != _TOKEN_URL:
        raise NotImplementedError(
            f"Unexpected Linear token_endpoint={token_endpoint!r}"
        )
    if code != _OAUTH_CODE:
        raise ValueError(f"Unexpected fake Linear OAuth code: {code!r}")
    if "/api/v1/auth/mcp/linear/connector/callback" not in redirect_uri:
        raise ValueError(f"Unexpected Linear redirect_uri={redirect_uri!r}")
    if client_id != _CLIENT_ID or client_secret != _CLIENT_SECRET:
        raise ValueError(
            "Unexpected Linear client credentials: "
            f"client_id={client_id!r} client_secret={client_secret!r}"
        )
    if not code_verifier:
        raise ValueError("Linear token exchange missing code_verifier.")
    return {
        "access_token": _ACCESS_TOKEN,
        "refresh_token": _REFRESH_TOKEN,
        "expires_in": 3600,
        "scope": "read write",
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
    if token_endpoint != _TOKEN_URL:
        raise NotImplementedError(
            f"Unexpected Linear token_endpoint={token_endpoint!r}"
        )
    if refresh_token != _REFRESH_TOKEN:
        raise ValueError(f"Unexpected fake Linear refresh token: {refresh_token!r}")
    if client_id != _CLIENT_ID or client_secret != _CLIENT_SECRET:
        raise ValueError(
            "Unexpected Linear refresh client credentials: "
            f"client_id={client_id!r} client_secret={client_secret!r}"
        )
    return {
        "access_token": _ACCESS_TOKEN,
        "refresh_token": _REFRESH_TOKEN,
        "expires_in": 3600,
        "scope": "read write",
        "token_type": "Bearer",
    }


class _FakeStreamableHttpClient(_StrictFakeMixin):
    _component_name = "streamablehttp_client"

    def __init__(
        self, url: str, *, headers: dict[str, str] | None = None, **kwargs: Any
    ):
        del kwargs
        if url != _MCP_URL:
            raise NotImplementedError(f"Unexpected Linear MCP url={url!r}")
        auth = (headers or {}).get("Authorization")
        if auth != f"Bearer {_ACCESS_TOKEN}":
            raise ValueError(f"Unexpected Linear MCP Authorization header: {auth!r}")
        self.url = url
        self.headers = headers or {}

    async def __aenter__(self) -> tuple[object, object, None]:
        return object(), object(), None

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        del exc_type, exc, tb


class _FakeClientSession(_StrictFakeMixin):
    _component_name = "ClientSession"

    def __init__(self, read: object, write: object):
        self.read = read
        self.write = write

    async def __aenter__(self) -> _FakeClientSession:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        del exc_type, exc, tb

    async def initialize(self) -> None:
        return None

    async def list_tools(self) -> SimpleNamespace:
        return SimpleNamespace(
            tools=[
                SimpleNamespace(
                    name="list_issues",
                    description="List Linear issues visible to the authenticated user.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Text to search for in Linear issues.",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of issues to return.",
                            },
                        },
                        "required": [],
                    },
                ),
                SimpleNamespace(
                    name="get_issue",
                    description="Get a Linear issue by id or identifier.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "Issue id or identifier.",
                            }
                        },
                        "required": ["id"],
                    },
                ),
            ]
        )

    async def call_tool(
        self, tool_name: str, *, arguments: dict[str, Any] | None = None
    ) -> SimpleNamespace:
        arguments = arguments or {}
        issue = _FIXTURE["issues"][0]

        if tool_name == "list_issues":
            query = str(arguments.get("query", ""))
            if query and issue["title"].lower() not in query.lower():
                raise ValueError(f"Unexpected Linear issue query: {query!r}")
            text = (
                f"{issue['identifier']} {issue['title']}\n"
                f"id: {issue['id']}\n"
                f"description: {issue['description']}"
            )
            return SimpleNamespace(content=[SimpleNamespace(text=text)])

        if tool_name == "get_issue":
            issue_id = arguments.get("id")
            if issue_id not in {issue["id"], issue["identifier"]}:
                raise ValueError(f"Unexpected Linear issue id: {issue_id!r}")
            text = (
                f"{issue['identifier']} {issue['title']}\n"
                f"id: {issue['id']}\n"
                f"description: {issue['description']}"
            )
            return SimpleNamespace(content=[SimpleNamespace(text=text)])

        raise NotImplementedError(f"Unexpected Linear MCP tool call: {tool_name!r}")


def _fake_streamablehttp_client(
    url: str, *, headers: dict[str, str] | None = None, **kwargs: Any
) -> _FakeStreamableHttpClient:
    return _FakeStreamableHttpClient(url, headers=headers, **kwargs)


async def _list_tools() -> SimpleNamespace:
    return await _FakeClientSession(object(), object()).list_tools()


async def _call_tool(tool_name: str, arguments: dict[str, Any]) -> SimpleNamespace:
    return await _FakeClientSession(object(), object()).call_tool(
        tool_name, arguments=arguments
    )


def install(active_patches: list[Any]) -> None:
    """Register Linear MCP OAuth/tool handlers with the shared dispatchers."""
    del active_patches
    mcp_oauth_runtime.register_service(
        mcp_url=_MCP_URL,
        discovery_metadata={
            "issuer": "https://mcp.linear.app",
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
        scope="read write",
        redirect_uri_substring="/api/v1/auth/mcp/linear/connector/callback",
    )
    mcp_runtime.register(
        url=_MCP_URL,
        expected_bearer=_ACCESS_TOKEN,
        list_tools=_list_tools,
        call_tool=_call_tool,
    )
