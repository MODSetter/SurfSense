"""One runtime request sent on to a plugin's server, and its answer streamed back as it came.

HTTP, not MCP: the runtime's own client keeps its sessions, timeouts and cancellation.
"""

from collections.abc import Callable
from dataclasses import dataclass

import httpx2
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse

# What MCP needs carried each way; a runtime's own authorization is never sent on, and a
# server's `WWW-Authenticate` never reaches the runtime, which would start a sign-in of its own.
_TO_SERVER = (
    "accept",
    "content-type",
    "mcp-session-id",
    "mcp-protocol-version",
    "last-event-id",
)
_TO_RUNTIME = ("content-type", "mcp-session-id", "cache-control")
# A server that does not accept within this is answered 502; a call itself may run as
# long as the runtime waits, since a scrape on SurfSense's plugin host runs minutes.
CONNECT_SECONDS = 10


@dataclass
class Sent:
    """A server's answer, open until streamed back or closed."""

    answer: httpx2.Response
    http: httpx2.AsyncClient

    async def close(self) -> None:
        await self.answer.aclose()
        await self.http.aclose()


async def send_on(
    request: Request, body: bytes, url: str, headers: dict[str, str]
) -> Sent:
    """Raises httpx2.HTTPError for a server that cannot be reached."""
    carried = {
        name: request.headers[name] for name in _TO_SERVER if name in request.headers
    }
    http = httpx2.AsyncClient(timeout=httpx2.Timeout(None, connect=CONNECT_SECONDS))
    try:
        sent = http.build_request(
            request.method, url, headers={**carried, **headers}, content=body
        )
        return Sent(await http.send(sent, stream=True), http)
    except BaseException:
        await http.aclose()
        raise


def streamed_back(sent: Sent, then: Callable[[], None] | None = None) -> Response:
    """`then` runs once the answer has ended, streamed whole or cut off."""
    headers = {
        name: sent.answer.headers[name]
        for name in _TO_RUNTIME
        if name in sent.answer.headers
    }

    async def closed() -> None:
        try:
            await sent.close()
        finally:
            if then is not None:
                then()

    return StreamingResponse(
        sent.answer.aiter_bytes(),
        status_code=sent.answer.status_code,
        headers=headers,
        background=BackgroundTask(closed),
    )


def unreachable() -> Response:
    return JSONResponse(
        {"detail": "the plugin's server could not be reached"}, status_code=502
    )
