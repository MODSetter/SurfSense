"""A real MCP server, from the official SDK, served on loopback for the client's tests."""

import json
import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations
from starlette.types import ASGIApp, Receive, Scope, Send


@contextmanager
def serving(app: ASGIApp) -> Iterator[str]:
    """Serve `app` on a free loopback port and yield its base URL."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning", lifespan="on"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]})
    thread.start()
    while not server.started:
        time.sleep(0.01)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join()


class RecordingHeaders:
    """Wraps an app and keeps the `authorization` header of every request it gets."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.authorizations: list[str | None] = []

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            headers = dict(scope["headers"])
            value = headers.get(b"authorization")
            self.authorizations.append(value.decode() if value else None)
        await self.app(scope, receive, send)


class FailingFirst:
    """Answers the first `times` requests for `method` with `status`, then passes them on."""

    def __init__(
        self, app: ASGIApp, method: str, times: int, status: int = 503
    ) -> None:
        self.app = app
        self.method = method
        self.times = times
        self.status = status
        self.seen = 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST":
            await self.app(scope, receive, send)
            return
        body = b""
        while True:
            event = await receive()
            body += event.get("body", b"")
            if not event.get("more_body"):
                break
        if json.loads(body).get("method") == self.method:
            self.seen += 1
            if self.seen <= self.times:
                await send(
                    {
                        "type": "http.response.start",
                        "status": self.status,
                        "headers": [],
                    }
                )
                await send({"type": "http.response.body", "body": b""})
                return
        replayed = False

        async def replay():
            nonlocal replayed
            if replayed:
                return await receive()
            replayed = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay, send)


def notes_server() -> MCPServer:
    """A plugin with two tools: a read-only search and a word count."""
    server = MCPServer("notes")

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def search(query: str) -> str:
        """Search the notes."""
        return f"found {query}"

    @server.tool()
    def count(text: str) -> dict[str, int]:
        """Count the words in a text."""
        return {"words": len(text.split())}

    return server


class RequiringToken:
    """Answers 401 to any request without `Bearer <token>`, as a server needing a key does."""

    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app = app
        self.expected = f"Bearer {token}".encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] == "http"
            and dict(scope["headers"]).get(b"authorization") != self.expected
        ):
            await send({"type": "http.response.start", "status": 401, "headers": []})
            await send({"type": "http.response.body", "body": b""})
            return
        await self.app(scope, receive, send)
