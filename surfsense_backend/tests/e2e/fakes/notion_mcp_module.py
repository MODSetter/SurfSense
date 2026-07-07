"""Strict Notion MCP OAuth/tool fakes for Playwright E2E.

Notion migrated from indexed OAuth to the hosted Notion MCP server
(``https://mcp.notion.com/mcp``, DCR/RFC 7591). This fake mirrors
``jira_module`` for the generic MCP OAuth + streamable-HTTP tool boundaries;
the older ``notion_module`` (a ``notion_client`` SDK stand-in) stays only to
satisfy production's import-time ``import notion_client``.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from tests.e2e.fakes import mcp_oauth_runtime, mcp_runtime

_AUTHORIZATION_URL = "https://mcp.notion.com/authorize"
_REGISTRATION_URL = "https://mcp.notion.com/register"
_TOKEN_URL = "https://mcp.notion.com/token"
_MCP_URL = "https://mcp.notion.com/mcp"

_CLIENT_ID = "fake-notion-mcp-client-id"
_CLIENT_SECRET = "fake-notion-mcp-client-secret"
_ACCESS_TOKEN = "fake-notion-mcp-access-token"
_REFRESH_TOKEN = "fake-notion-mcp-refresh-token"
_OAUTH_CODE = "fake-notion-oauth-code"

# Keep in sync with FAKE_NOTION_PAGES / CANARY_TOKENS.notionCanary in
# surfsense_web/tests/helpers/canary.ts.
_CANARY_TOKEN = "SURFSENSE_E2E_CANARY_TOKEN_NOTION_001"
_CANARY_PAGE_ID = "fake-notion-page-canary-001"
_CANARY_TITLE = "E2E Canary Notion Page"
_WORKSPACE_NAME = "SurfSense E2E Notion Workspace"


async def _list_tools() -> SimpleNamespace:
    return SimpleNamespace(
        tools=[
            SimpleNamespace(
                name="search",
                description="Search the connected Notion workspace for pages and databases.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Text to search Notion pages for.",
                        }
                    },
                    "required": ["query"],
                },
            ),
            SimpleNamespace(
                name="fetch",
                description="Fetch the full contents of a Notion page by id.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "The Notion page id to fetch.",
                        }
                    },
                    "required": ["id"],
                },
            ),
        ]
    )


async def _call_tool(
    tool_name: str, arguments: dict[str, Any] | None = None
) -> SimpleNamespace:
    arguments = arguments or {}

    if tool_name == "search":
        query = str(arguments.get("query", ""))
        if _CANARY_TITLE.lower() not in query.lower():
            raise ValueError(f"Unexpected Notion search query: {query!r}")
        text = (
            f"{_CANARY_TITLE}\n"
            f"id: {_CANARY_PAGE_ID}\n"
            f"workspace: {_WORKSPACE_NAME}\n"
            f"snippet: {_CANARY_TOKEN}"
        )
        return SimpleNamespace(content=[SimpleNamespace(text=text)])

    if tool_name == "fetch":
        page_id = str(arguments.get("id", ""))
        if page_id != _CANARY_PAGE_ID:
            raise ValueError(f"Unexpected Notion fetch id: {page_id!r}")
        text = f"{_CANARY_TITLE}\n\n{_CANARY_TOKEN}"
        return SimpleNamespace(content=[SimpleNamespace(text=text)])

    raise NotImplementedError(f"Unexpected Notion MCP tool call: {tool_name!r}")


def install(active_patches: list[Any]) -> None:
    """Register Notion MCP OAuth/tool handlers with the shared dispatchers."""
    del active_patches
    mcp_oauth_runtime.register_service(
        mcp_url=_MCP_URL,
        discovery_metadata={
            "issuer": "https://mcp.notion.com",
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
        redirect_uri_substring="/api/v1/auth/mcp/notion/connector/callback",
    )
    mcp_runtime.register(
        url=_MCP_URL,
        expected_bearer=_ACCESS_TOKEN,
        list_tools=_list_tools,
        call_tool=_call_tool,
    )
