"""A plugin's MCP server, listed through the official SDK's client over Streamable HTTP.

SurfSense lists a plugin's tools itself, to connect it and to notice tools that change;
the agent's opencode calls them with its own client. Each listing opens its own SDK
client: the SDK's tasks must close in the task that opened them.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import httpx2
from mcp.client.client import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError

from modules.plugins.remote.mcp_client.http_failure import unreachable
from modules.plugins.remote.mcp_client.remote_tool import RemoteTool
from modules.plugins.remote.mcp_client.retries import retried
from modules.plugins.remote.mcp_client.sdk_errors import translated
from modules.plugins.remote.mcp_client.session_expired import SessionExpiredError
from modules.plugins.remote.mcp_client.unwrapped import unwrapped


class McpSession:
    def __init__(self, url: str, headers: dict[str, str] | None = None) -> None:
        self._url = url
        self._headers = headers or {}

    async def list_tools(self) -> list[RemoteTool]:
        return await retried(self._list_in_fresh_session)

    async def close(self) -> None:
        """Nothing stays open between listings."""

    async def _list_in_fresh_session(self) -> list[RemoteTool]:
        """List once more on a new session if the server forgot ours: it handled nothing."""
        try:
            return await self._list()
        except SessionExpiredError:
            return await self._list()

    async def _list(self) -> list[RemoteTool]:
        failed_status: list[int] = []
        reasons: list[str | None] = []

        async def record_failure(response: httpx2.Response) -> None:
            if response.status_code >= 400:
                failed_status.append(response.status_code)
                reasons.append(await _refusal_reason(response))

        try:
            async with self._client(record_failure) as client:
                return await _every_page(client)
        except (MCPError, httpx2.TransportError, BaseExceptionGroup) as raised:
            error = unwrapped(raised)
            if isinstance(error, MCPError):
                status = failed_status[-1] if failed_status else None
                reason = reasons[-1] if reasons else None
                raise translated(error, status, reason) from error
            if isinstance(error, httpx2.TransportError):
                raise unreachable(error) from error
            raise

    @asynccontextmanager
    async def _client(
        self, on_response: Callable[[httpx2.Response], Awaitable[None]]
    ) -> AsyncIterator[Client]:
        async with (
            httpx2.AsyncClient(
                headers=self._headers, event_hooks={"response": [on_response]}
            ) as http,
            Client(streamable_http_client(self._url, http_client=http)) as client,
        ):
            yield client


async def _refusal_reason(response: httpx2.Response) -> str | None:
    """A 401 or 403's `{"reason": ...}`, which SurfSense's plugin host sends; None otherwise."""
    if response.status_code not in (401, 403):
        return None
    await response.aread()
    try:
        reason = response.json().get("reason")
    except (ValueError, AttributeError):
        return None
    return reason if isinstance(reason, str) else None


async def _every_page(client: Client) -> list[RemoteTool]:
    tools: list[RemoteTool] = []
    cursor: str | None = None
    while True:
        page = await client.list_tools(cursor=cursor, cache_mode="bypass")
        tools += [
            RemoteTool.from_listing(tool.model_dump(by_alias=True, exclude_none=True))
            for tool in page.tools
        ]
        cursor = page.next_cursor
        if not cursor:
            return tools
