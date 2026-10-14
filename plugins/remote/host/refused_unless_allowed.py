"""A plugin's server behind its `access`: a refused request never reaches it."""

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from mcp_server.access import Access


class RefusedUnlessAllowed:
    def __init__(self, app: ASGIApp, access: Access) -> None:
        self.app = app
        self.access = access

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            refusal = await self.access.refusal(Headers(scope=scope))
            if refusal is not None:
                response = JSONResponse({"reason": refusal.reason}, refusal.status)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
