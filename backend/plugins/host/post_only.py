"""A plugin's MCP endpoint takes POST only: no copy keeps a stream open for a client."""

import json

from starlette.types import ASGIApp, Receive, Scope, Send

# The SDK's own code for a request it does not take.
INVALID_REQUEST = -32600
_REFUSED = {"GET", "DELETE"}


class PostOnly:
    """GET and DELETE on `/mcp` are 405 with `Allow: POST`; anything else goes through.

    Without sessions, the SDK answers the client's fire-and-forget GET with an
    event stream that never carries a message, holding a connection, a task and
    a ping every 15 s per plugin per agent. The client reads 405 as "no stream".
    There is no session to DELETE.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] == "http"
            and scope["method"] in _REFUSED
            and route_path(scope).rstrip("/") == "/mcp"
        ):
            body = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": INVALID_REQUEST, "message": "Method Not Allowed"},
                }
            ).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 405,
                    "headers": [
                        (b"allow", b"POST"),
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return
        await self.app(scope, receive, send)


def route_path(scope: Scope) -> str:
    """The path under the plugin's mount, as Starlette's own routing reads it."""
    path: str = scope["path"]
    root_path: str = scope.get("root_path", "")
    return path[len(root_path) :] if root_path and path.startswith(root_path) else path
