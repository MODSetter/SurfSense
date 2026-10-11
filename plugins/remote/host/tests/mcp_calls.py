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


async def call(url: str, tool: str, arguments: dict[str, Any]) -> Any:
    async with (
        httpx2.AsyncClient() as http,
        Client(streamable_http_client(url, http_client=http)) as client,
    ):
        return await client.call_tool(tool, arguments)
