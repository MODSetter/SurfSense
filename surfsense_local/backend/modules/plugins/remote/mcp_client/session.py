"""A plugin's MCP server, through the official SDK's client over Streamable HTTP.

SurfSense lists a plugin's tools itself, to connect it and to notice tools that change;
the agent's opencode calls them with its own client. SurfSense calls a tool itself only
for a user's action outside a thread: pulling a link into Sources. Each request opens
its own SDK client: the SDK's tasks must close in the task that opened them.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import httpx2
from mcp.client.client import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError
from mcp_types import CallToolResult

from modules.plugins.remote.mcp_client.http_failure import refused, unreachable
from modules.plugins.remote.mcp_client.remote_tool import RemoteTool
from modules.plugins.remote.mcp_client.retries import retried
from modules.plugins.remote.mcp_client.scope_challenge import challenged_scopes
from modules.plugins.remote.mcp_client.sdk_errors import translated
from modules.plugins.remote.mcp_client.session_expired import SessionExpiredError
from modules.plugins.remote.mcp_client.unwrapped import unwrapped


class McpSession:
    def __init__(self, url: str, headers: dict[str, str] | None = None) -> None:
        self._url = url
        self._headers = headers or {}

    async def list_tools(self) -> list[RemoteTool]:
        return await retried(self._list_in_fresh_session)

    async def call_tool(
        self, name: str, arguments: dict[str, object], read_seconds: float
    ) -> CallToolResult:
        """Never retried: a call may have done its work before it failed."""

        async def call(client: Client) -> CallToolResult:
            return await client.call_tool(
                name, arguments, read_timeout_seconds=read_seconds
            )

        return await self._run(call, httpx2.Timeout(30, read=read_seconds))

    async def close(self) -> None:
        """Nothing stays open between requests."""

    async def _list_in_fresh_session(self) -> list[RemoteTool]:
        """List once more on a new session if the server forgot ours: it handled nothing."""
        try:
            return await self._list()
        except SessionExpiredError:
            return await self._list()

    async def _list(self) -> list[RemoteTool]:
        return await self._run(_every_page)

    async def _run[T](
        self,
        work: Callable[[Client], Awaitable[T]],
        timeout: httpx2.Timeout | None = None,
    ) -> T:
        failed_status: list[int] = []
        reasons: list[str | None] = []
        scopes: list[list[str] | None] = []

        async def record_failure(response: httpx2.Response) -> None:
            if response.status_code >= 400:
                failed_status.append(response.status_code)
                reasons.append(await _refusal_reason(response))
                scopes.append(challenged_scopes(response))

        try:
            async with self._client(record_failure, timeout) as client:
                return await work(client)
        except (MCPError, httpx2.TransportError, BaseExceptionGroup) as raised:
            error = unwrapped(raised)
            if isinstance(error, MCPError):
                status = failed_status[-1] if failed_status else None
                reason = reasons[-1] if reasons else None
                asked = scopes[-1] if scopes else None
                raise translated(error, status, reason, asked) from error
            if isinstance(error, httpx2.TransportError):
                raise unreachable(error) from error
            if isinstance(error, httpx2.HTTPStatusError):
                raise _stream_refused(error, reasons, scopes) from error
            raise
        except httpx2.HTTPStatusError as error:
            raise _stream_refused(error, reasons, scopes) from error

    @asynccontextmanager
    async def _client(
        self,
        on_response: Callable[[httpx2.Response], Awaitable[None]],
        call_timeout: httpx2.Timeout | None = None,
    ) -> AsyncIterator[Client]:
        """`call_timeout` for a call, which may wait minutes; a listing keeps httpx's default."""
        hooks = {"response": [on_response]}
        timeouts = {"timeout": call_timeout} if call_timeout is not None else {}
        async with (
            httpx2.AsyncClient(
                headers=self._headers, event_hooks=hooks, **timeouts
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


def _stream_refused(
    error: httpx2.HTTPStatusError,
    reasons: list[str | None],
    scopes: list[list[str] | None],
) -> Exception:
    """A stream refused outright is raised as is: kept as the status it answered."""
    return refused(
        error.response.status_code,
        reasons[-1] if reasons else None,
        scopes[-1] if scopes else None,
    )
