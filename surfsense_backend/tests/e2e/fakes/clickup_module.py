"""Strict ClickUp MCP OAuth/tool fakes for Playwright E2E."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from tests.e2e.fakes import mcp_oauth_runtime, mcp_runtime

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "clickup_tasks.json"

_AUTHORIZATION_URL = "https://mcp.clickup.com/authorize"
_REGISTRATION_URL = "https://mcp.clickup.com/register"
_TOKEN_URL = "https://mcp.clickup.com/token"
_MCP_URL = "https://mcp.clickup.com/mcp"

_CLIENT_ID = "fake-clickup-mcp-client-id"
_CLIENT_SECRET = "fake-clickup-mcp-client-secret"
_ACCESS_TOKEN = "fake-clickup-mcp-access-token"
_REFRESH_TOKEN = "fake-clickup-mcp-refresh-token"
_OAUTH_CODE = "fake-clickup-oauth-code"


def _load_fixture() -> dict[str, Any]:
    with _FIXTURE_PATH.open() as f:
        return json.load(f)


_FIXTURE = _load_fixture()


def _task_text(task: dict[str, Any]) -> str:
    return (
        f"{task['name']}\n"
        f"id: {task['id']}\n"
        f"workspace: {task['workspace_name']} ({task['workspace_id']})\n"
        f"list: {task['list_name']}\n"
        f"status: {task['status']}\n"
        f"description: {task['description']}"
    )


async def _list_tools() -> SimpleNamespace:
    return SimpleNamespace(
        tools=[
            SimpleNamespace(
                name="clickup_search",
                description="Search ClickUp tasks visible to the authenticated user.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Text to search for in ClickUp tasks.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of tasks to return.",
                        },
                    },
                    "required": ["query"],
                },
            ),
            SimpleNamespace(
                name="clickup_get_task",
                description="Get a ClickUp task by id.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "ClickUp task id.",
                        }
                    },
                    "required": ["task_id"],
                },
            ),
        ]
    )


async def _call_tool(
    tool_name: str, arguments: dict[str, Any] | None = None
) -> SimpleNamespace:
    arguments = arguments or {}
    task = _FIXTURE["tasks"][0]

    if tool_name == "clickup_search":
        query = str(arguments.get("query", ""))
        if query and task["name"].lower() not in query.lower():
            raise ValueError(f"Unexpected ClickUp task query: {query!r}")
        return SimpleNamespace(content=[SimpleNamespace(text=_task_text(task))])

    if tool_name == "clickup_get_task":
        task_id = arguments.get("task_id")
        if task_id != task["id"]:
            raise ValueError(f"Unexpected ClickUp task id: {task_id!r}")
        return SimpleNamespace(content=[SimpleNamespace(text=_task_text(task))])

    raise NotImplementedError(f"Unexpected ClickUp MCP tool call: {tool_name!r}")


def install(active_patches: list[Any]) -> None:
    """Register ClickUp MCP OAuth/tool handlers with the shared dispatchers."""
    del active_patches
    mcp_oauth_runtime.register_service(
        mcp_url=_MCP_URL,
        discovery_metadata={
            "issuer": "https://mcp.clickup.com",
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
        redirect_uri_substring="/api/v1/auth/mcp/clickup/connector/callback",
    )
    mcp_runtime.register(
        url=_MCP_URL,
        expected_bearer=_ACCESS_TOKEN,
        list_tools=_list_tools,
        call_tool=_call_tool,
    )
