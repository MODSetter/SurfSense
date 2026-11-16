"""`GET /license`: whether the request's license unlocks the paid plugins, asked once for all.

The app asks this rather than listing each paid plugin. It is the paid plugins' own check,
so the answers, cache and grace are contract 2's, and a build without one has no route.
"""

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from mcp_server.access import Access


def license_route(access: Access) -> Route:
    async def license_status(request: Request) -> JSONResponse:
        refusal = await access.refusal(request.headers)
        if refusal is not None:
            return JSONResponse({"reason": refusal.reason}, refusal.status)
        return JSONResponse({"status": "valid"})

    return Route("/license", license_status, methods=["GET"])
