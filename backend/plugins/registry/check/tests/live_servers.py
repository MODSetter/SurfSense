"""Real MCP servers from the official SDK, and the ways a listed one can go wrong, on loopback."""

import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send


@contextmanager
def serving(app: ASGIApp) -> Iterator[str]:
    """Serve `app` on a free loopback port and yield its base URL."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    config = uvicorn.Config(
        app, log_level="warning", lifespan="on", timeout_graceful_shutdown=1
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]})
    thread.start()
    while not server.started:
        time.sleep(0.01)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join()


def closed_port() -> str:
    """A loopback address nothing answers on."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return f"http://127.0.0.1:{port}/mcp"


def docs_server(annotated: bool = True) -> ASGIApp:
    """An MCP server with two tools, served at `/mcp` without sessions."""
    return _docs(annotated).streamable_http_app(stateless_http=True)


def docs_sse_server() -> ASGIApp:
    """The same tools on the older HTTP+SSE transport, at `/sse`."""
    return _docs(True).sse_app()


def _docs(annotated: bool) -> MCPServer:
    server = MCPServer("docs")
    hints = ToolAnnotations(readOnlyHint=True) if annotated else None

    @server.tool(annotations=hints)
    def search_docs(query: str) -> str:
        """Search the docs."""
        return f"found {query}"

    @server.tool(annotations=hints)
    def read_page(path: str) -> str:
        """Read one page."""
        return f"page {path}"

    return server


class RequiringKey:
    """Answers 401 to a request without a key, as a server that takes one does."""

    def __init__(self, app: ASGIApp, www_authenticate: str | None = None) -> None:
        self.app = app
        self.www_authenticate = www_authenticate

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and b"authorization" not in dict(scope["headers"]):
            headers = []
            if self.www_authenticate:
                headers.append((b"www-authenticate", self.www_authenticate.encode()))
            await send(
                {"type": "http.response.start", "status": 401, "headers": headers}
            )
            await send({"type": "http.response.body", "body": b""})
            return
        await self.app(scope, receive, send)


def not_mcp() -> ASGIApp:
    """A web server with no MCP endpoint: every path is 404."""

    async def missing(_: Request) -> Response:
        return Response(status_code=404)

    return Starlette(routes=[Route("/{path:path}", missing, methods=["GET", "POST"])])


def authorization_server(
    *, registration: bool = True, metadata_document: bool = False
) -> ASGIApp:
    """RFC 8414 metadata naming its endpoints on its own origin."""

    async def metadata(request: Request) -> JSONResponse:
        origin = str(request.base_url).rstrip("/")
        body = {
            "issuer": origin,
            "authorization_endpoint": f"{origin}/authorize",
            "token_endpoint": f"{origin}/token",
            "response_types_supported": ["code"],
            "code_challenge_methods_supported": ["S256"],
        }
        if registration:
            body["registration_endpoint"] = f"{origin}/register"
        if metadata_document:
            body["client_id_metadata_document_supported"] = True
        return JSONResponse(body)

    return Starlette(
        routes=[Route("/.well-known/oauth-authorization-server", metadata)]
    )


def oauth_server(authorization_server_url: str | None) -> ASGIApp:
    """An MCP server that asks for OAuth, naming its authorization server (RFC 9728).

    With no authorization server it answers 401 and publishes no metadata.
    """

    async def resource(request: Request) -> JSONResponse:
        origin = str(request.base_url).rstrip("/")
        return JSONResponse(
            {
                "resource": f"{origin}/mcp",
                "authorization_servers": [authorization_server_url],
            }
        )

    async def refuse(request: Request) -> Response:
        origin = str(request.base_url).rstrip("/")
        named = f'Bearer resource_metadata="{origin}/.well-known/oauth-protected-resource/mcp"'
        return Response(
            status_code=401,
            headers={
                "www-authenticate": named if authorization_server_url else "Bearer"
            },
        )

    routes = [Route("/mcp", refuse, methods=["GET", "POST", "DELETE"])]
    if authorization_server_url:
        routes.append(Route("/.well-known/oauth-protected-resource/mcp", resource))
    return Starlette(routes=routes)


def entry(url: str, **overrides) -> dict:
    """A registry entry for a server on loopback; the live check reads only its server."""
    found = {
        "id": "docs",
        "kind": "remote",
        "verification": "community",
        "name": "Docs",
        "description": "Search the docs.",
        "author": "Docs Project",
        "url": url,
        "auth": {"type": "none"},
        "hosts": ["127.0.0.1"],
        "access": "free",
        "tools": ["read_page", "search_docs"],
    }
    found.update(overrides)
    return found


SECRET = "SECRET-TOKEN-XYZ"


def answering_secret() -> ASGIApp:
    """An internal service, such as a cloud metadata endpoint, answering credentials."""

    async def credentials(_: Request) -> JSONResponse:
        return JSONResponse({"AccessKeyId": "AKIA-123", "Token": SECRET})

    return Starlette(
        routes=[Route("/{path:path}", credentials, methods=["GET", "POST"])]
    )
