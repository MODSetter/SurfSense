"""`POST /cancel`: the app's Stop, for every call its thread has running on any copy."""

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from host.calls_in_flight import CALLS_HEADER, caller
from host.cancel_broadcast import CancelBroadcast


def cancel_route(broadcast: CancelBroadcast) -> Route:
    async def cancel(request: Request) -> Response:
        token = request.headers.get(CALLS_HEADER)
        if not token:
            return JSONResponse({"reason": "missing_token"}, 400)
        await broadcast.publish(caller(request.headers.get("authorization", "")), token)
        return Response(status_code=202)

    return Route("/cancel", cancel, methods=["POST"])
