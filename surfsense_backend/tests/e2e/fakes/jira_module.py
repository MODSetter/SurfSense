"""Strict Atlassian (Jira + Confluence) MCP OAuth/tool fakes for Playwright E2E.

Jira and Confluence share one hosted Atlassian Rovo MCP server
(``https://mcp.atlassian.com/v1/mcp``) and one OAuth surface. Because the MCP
OAuth/runtime dispatchers are keyed by URL, a single handler here serves both
connectors; production keeps their tool sets disjoint via each service's
``allowed_tools`` curation. The OAuth ``redirect_uri`` substring is therefore
relaxed to the shared ``/api/v1/auth/mcp/`` prefix so both the
``.../mcp/jira/...`` and ``.../mcp/confluence/...`` callbacks validate.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from tests.e2e.fakes import mcp_oauth_runtime, mcp_runtime

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "jira_issues.json"

_AUTHORIZATION_URL = "https://mcp.atlassian.com/v1/authorize"
_REGISTRATION_URL = "https://cf.mcp.atlassian.com/v1/register"
_TOKEN_URL = "https://cf.mcp.atlassian.com/v1/token"
_MCP_URL = "https://mcp.atlassian.com/v1/mcp"

_CLIENT_ID = "fake-jira-mcp-client-id"
_CLIENT_SECRET = "fake-jira-mcp-client-secret"
_ACCESS_TOKEN = "fake-jira-mcp-access-token"
_REFRESH_TOKEN = "fake-jira-mcp-refresh-token"
_OAUTH_CODE = "fake-jira-oauth-code"

# Confluence canary — keep in sync with FAKE_CONFLUENCE_PAGES /
# CANARY_TOKENS.confluenceCanary in surfsense_web/tests/helpers/canary.ts.
_CONFLUENCE_TOKEN = "SURFSENSE_E2E_CANARY_TOKEN_CONFLUENCE_001"
_CONFLUENCE_PAGE_ID = "fake-confluence-page-canary-001"
_CONFLUENCE_TITLE = "E2E Canary Confluence Page"
_CONFLUENCE_SPACE_ID = "fake-confluence-space-001"


def _load_fixture() -> dict[str, Any]:
    with _FIXTURE_PATH.open() as f:
        return json.load(f)


_FIXTURE = _load_fixture()


def _issue_text(issue: dict[str, Any]) -> str:
    return (
        f"{issue['key']} {issue['summary']}\n"
        f"id: {issue['id']}\n"
        f"description: {issue['description']}"
    )


async def _list_tools() -> SimpleNamespace:
    return SimpleNamespace(
        tools=[
            SimpleNamespace(
                name="getAccessibleAtlassianResources",
                description="Get Jira sites accessible to the authenticated Atlassian user.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            SimpleNamespace(
                name="searchJiraIssuesUsingJql",
                description="Search Jira issues using a Jira Query Language expression.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "jql": {
                            "type": "string",
                            "description": "JQL query used to search Jira issues.",
                        },
                        "maxResults": {
                            "type": "integer",
                            "description": "Maximum number of matching issues to return.",
                        },
                    },
                    "required": ["jql"],
                },
            ),
            SimpleNamespace(
                name="searchConfluenceUsingCql",
                description="Search Confluence content using a CQL expression.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "cql": {
                            "type": "string",
                            "description": "CQL query used to search Confluence content.",
                        }
                    },
                    "required": ["cql"],
                },
            ),
            SimpleNamespace(
                name="getConfluencePage",
                description="Fetch a Confluence page's body by id.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "pageId": {
                            "type": "string",
                            "description": "The Confluence page id to fetch.",
                        }
                    },
                    "required": ["pageId"],
                },
            ),
        ]
    )


async def _call_tool(
    tool_name: str, arguments: dict[str, Any] | None = None
) -> SimpleNamespace:
    arguments = arguments or {}
    site = _FIXTURE["site"]
    issue = _FIXTURE["issues"][0]

    if tool_name == "getAccessibleAtlassianResources":
        if arguments:
            raise ValueError(
                f"Unexpected Jira getAccessibleAtlassianResources args: {arguments!r}"
            )
        text = f"{site['name']}\ncloud_id: {site['cloud_id']}\nurl: {site['url']}"
        return SimpleNamespace(content=[SimpleNamespace(text=text)])

    if tool_name == "searchJiraIssuesUsingJql":
        jql = str(arguments.get("jql", ""))
        if (
            issue["summary"].lower() not in jql.lower()
            and issue["key"].lower() not in jql.lower()
        ):
            raise ValueError(f"Unexpected Jira JQL query: {jql!r}")
        text = _issue_text(issue)
        return SimpleNamespace(content=[SimpleNamespace(text=text)])

    if tool_name == "searchConfluenceUsingCql":
        cql = str(arguments.get("cql", ""))
        if _CONFLUENCE_TITLE.lower() not in cql.lower():
            raise ValueError(f"Unexpected Confluence CQL query: {cql!r}")
        text = (
            f"{_CONFLUENCE_TITLE}\n"
            f"id: {_CONFLUENCE_PAGE_ID}\n"
            f"space: {_CONFLUENCE_SPACE_ID}\n"
            f"excerpt: {_CONFLUENCE_TOKEN}"
        )
        return SimpleNamespace(content=[SimpleNamespace(text=text)])

    if tool_name == "getConfluencePage":
        page_id = str(arguments.get("pageId", ""))
        if page_id != _CONFLUENCE_PAGE_ID:
            raise ValueError(f"Unexpected Confluence page id: {page_id!r}")
        text = f"{_CONFLUENCE_TITLE}\n\n{_CONFLUENCE_TOKEN}"
        return SimpleNamespace(content=[SimpleNamespace(text=text)])

    raise NotImplementedError(f"Unexpected Atlassian MCP tool call: {tool_name!r}")


def install(active_patches: list[Any]) -> None:
    """Register the shared Atlassian (Jira + Confluence) MCP handlers."""
    del active_patches
    mcp_oauth_runtime.register_service(
        mcp_url=_MCP_URL,
        discovery_metadata={
            "issuer": "https://mcp.atlassian.com",
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
        scope="read:jira-work read:confluence-content.all read:me write:jira-work",
        # Shared Atlassian server serves both Jira and Confluence connectors, so
        # accept either service's callback under the common MCP OAuth prefix.
        redirect_uri_substring="/api/v1/auth/mcp/",
    )
    mcp_runtime.register(
        url=_MCP_URL,
        expected_bearer=_ACCESS_TOKEN,
        list_tools=_list_tools,
        call_tool=_call_tool,
    )
