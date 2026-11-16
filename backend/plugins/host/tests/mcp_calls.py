"""A plugin reached as the app reaches it: the official MCP client over Streamable HTTP."""

from typing import Any

import httpx2
from mcp.client.client import Client
from mcp.client.streamable_http import streamable_http_client


async def tool_names(url: str, headers: dict[str, str] | None = None) -> list[str]:
    async with (
        httpx2.AsyncClient(headers=headers or {}) as http,
        Client(streamable_http_client(url, http_client=http)) as client,
    ):
        return [tool.name for tool in (await client.list_tools()).tools]


async def call(
    url: str,
    tool: str,
    arguments: dict[str, Any],
    headers: dict[str, str] | None = None,
    progress: list[float] | None = None,
) -> Any:
    """`progress` collects each progress notification the call sends."""

    async def heard(value: float, total: float | None, message: str | None) -> None:
        if progress is not None:
            progress.append(value)

    async with (
        httpx2.AsyncClient(headers=headers or {}) as http,
        Client(streamable_http_client(url, http_client=http)) as client,
    ):
        return await client.call_tool(tool, arguments, progress_callback=heard)


# What opencode's client sends: the 2025-11-25 handshake, over Streamable HTTP.
HANDSHAKE_HEADERS = {
    "accept": "application/json, text/event-stream",
    "content-type": "application/json",
    "mcp-protocol-version": "2025-11-25",
}


def raw_request(
    url: str, body: dict[str, Any], headers: dict[str, str] | None = None
) -> httpx2.Response:
    """One JSON-RPC message as its own HTTP request, with no session unless given one."""
    return httpx2.post(
        url, json=body, headers={**HANDSHAKE_HEADERS, **(headers or {})}, timeout=70
    )
