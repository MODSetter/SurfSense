"""A real MCP server, from the official SDK, served on loopback for the client's tests."""

import json
import socket
import threading
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send


@dataclass(frozen=True)
class Certificate:
    """A self-signed certificate for `localhost`, which a client is told to trust."""

    cert: Path
    key: Path


def localhost_certificate(folder: Path) -> Certificate:
    """Written into `folder`; valid for a day either side of now."""
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), True)
        .sign(key, hashes.SHA256())
    )
    made = Certificate(folder / "localhost.pem", folder / "localhost-key.pem")
    made.cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    made.key.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return made


@contextmanager
def serving(app: ASGIApp, tls: Certificate | None = None) -> Iterator[str]:
    """Serve `app` on a free loopback port and yield its base URL.

    With `tls`, it is `https://localhost:<port>`, as a remote plugin is reached.
    """
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    # A client holding its stream open, as opencode does, must not keep the server up.
    config = uvicorn.Config(
        app,
        log_level="warning",
        lifespan="on",
        timeout_graceful_shutdown=1,
        ssl_certfile=tls and str(tls.cert),
        ssl_keyfile=tls and str(tls.key),
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]})
    thread.start()
    while not server.started:
        time.sleep(0.01)
    try:
        yield f"https://localhost:{port}" if tls else f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join()


class RecordingHeaders:
    """Wraps an app and keeps one header, `authorization` unless named, of every request."""

    def __init__(self, app: ASGIApp, header: str = "authorization") -> None:
        self.app = app
        self.header = header.encode()
        self.authorizations: list[str | None] = []

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            headers = dict(scope["headers"])
            value = headers.get(self.header)
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


class RecordingMethods:
    """Wraps an app and keeps the JSON-RPC method of every request it gets."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.methods: list[str] = []

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
        self.methods.append(json.loads(body).get("method", ""))
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


def amazon_server() -> MCPServer:
    """A stand-in for SurfSense's Amazon plugin: one read-only search."""
    server = MCPServer("amazon")

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    def search_products(query: str) -> str:
        """Search Amazon's products."""
        return f"products about {query}"

    return server


class RequiringLicense:
    """Answers as the plugin host's license check does: `{"reason": ...}` with 401 or 403.

    `refused` maps a key to its 403 reason; any other key is valid.
    """

    def __init__(self, app: ASGIApp, refused: dict[str, str] | None = None) -> None:
        self.app = app
        self.refused = refused or {}
        self.authorizations: list[str | None] = []
        self.calls_tokens: list[str | None] = []

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        value = headers.get(b"authorization")
        authorization = value.decode() if value else None
        self.authorizations.append(authorization)
        calls = headers.get(b"x-surfsense-calls")
        self.calls_tokens.append(calls.decode() if calls else None)
        scheme, _, key = (authorization or "").partition(" ")
        if scheme != "License" or not key:
            await JSONResponse({"reason": "missing_license"}, 401)(scope, receive, send)
        elif key in self.refused:
            await JSONResponse({"reason": self.refused[key]}, 403)(scope, receive, send)
        else:
            await self.app(scope, receive, send)


def plugin_host(
    plugin_id: str,
    server: MCPServer,
    around=lambda app: app,
    cancels: list[dict[str, str | None]] | None = None,
) -> Starlette:
    """A plugin host serving one plugin at `/<id>/mcp`, as SurfSense's does.

    `cancels` keeps the sign-in and thread token of each `POST /cancel` it gets.
    """

    @asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        async with server.session_manager.run():
            yield

    async def cancel(request: Request) -> Response:
        if cancels is not None:
            cancels.append(
                {
                    "authorization": request.headers.get("authorization"),
                    "x-surfsense-calls": request.headers.get("x-surfsense-calls"),
                }
            )
        return Response(status_code=202)

    app = around(server.streamable_http_app())
    return Starlette(
        routes=[
            Route("/cancel", cancel, methods=["POST"]),
            Mount(f"/{plugin_id}", app=app),
        ],
        lifespan=lifespan,
    )
