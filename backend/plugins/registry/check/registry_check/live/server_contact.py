"""Listing a server's tools with the MCP client the app uses, and what stopped it if not."""

from dataclasses import dataclass
from typing import Any

import anyio
import httpx2
from mcp.client.client import Client
from mcp.client.streamable_http import streamable_http_client

from registry_check.live.failure_reason import failure_reason
from registry_check.live.web import TIMEOUT_SECONDS, web_client

SIGN_IN_STATUSES = (401, 403)


@dataclass(frozen=True)
class Listed:
    tools: list[dict[str, Any]]


@dataclass(frozen=True)
class SignInAsked:
    status: int


@dataclass(frozen=True)
class Unreachable:
    reason: str


@dataclass(frozen=True)
class NotMcp:
    reason: str
    # The 4xx a server refusing without a key answered, other than 401 or 403.
    status: int | None = None


Contact = Listed | SignInAsked | Unreachable | NotMcp


async def contact(url: str) -> Contact:
    """With no credentials: what a user's app meets before signing in, over
    Streamable HTTP, the only transport the app speaks."""
    refused: list[int] = []
    failed: list[int] = []

    async def record(response: httpx2.Response) -> None:
        if response.status_code in SIGN_IN_STATUSES:
            refused.append(response.status_code)
        elif response.status_code >= 400:
            failed.append(response.status_code)

    try:
        # Listing pages through a cursor can take a few requests.
        with anyio.fail_after(TIMEOUT_SECONDS * 2):
            async with (
                web_client(on_response=record) as http,
                Client(streamable_http_client(url, http_client=http)) as client,
            ):
                return Listed(await _every_page(client))
    except TimeoutError:
        return Unreachable("timed out")
    except Exception as raised:
        if refused:
            return SignInAsked(refused[-1])
        error = _innermost(raised)
        if isinstance(error, httpx2.TransportError):
            return Unreachable(failure_reason(error))
        if failed:
            return NotMcp(f"it answered {failed[-1]}", failed[-1])
        return NotMcp("its answer is not MCP")


async def answers_sse(url: str) -> bool:
    """Whether the address opens an event stream on GET, as a server on the
    older HTTP+SSE transport does."""
    try:
        async with (
            web_client() as http,
            http.stream("GET", url, headers={"accept": "text/event-stream"}) as reply,
        ):
            kind = reply.headers.get("content-type", "")
            return reply.status_code == 200 and kind.startswith("text/event-stream")
    except httpx2.HTTPError:
        return False


async def _every_page(client: Client) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        page = await client.list_tools(cursor=cursor, cache_mode="bypass")
        tools += [t.model_dump(by_alias=True, exclude_none=True) for t in page.tools]
        cursor = page.next_cursor
        if not cursor:
            return tools


def _innermost(error: BaseException) -> BaseException:
    """The SDK's task groups wrap the failure; the first leaf says what it was."""
    while isinstance(error, BaseExceptionGroup) and error.exceptions:
        error = error.exceptions[0]
    if isinstance(error.__cause__, httpx2.TransportError):
        return error.__cause__
    return error
