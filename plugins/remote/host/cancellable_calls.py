"""A plugin's server, its calls run where a Stop for their thread can end them."""

import json
from typing import Any

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from host.calls_in_flight import CALLS_HEADER, CallsInFlight, caller

# JSON-RPC has no code for it; this is the one language servers use.
REQUEST_CANCELLED = -32800


class CancellableCalls:
    """opencode cancels with a message no stateless copy can match to its call, so the app's Stop does."""

    def __init__(self, app: ASGIApp, calls: CallsInFlight) -> None:
        self.app = app
        self.calls = calls

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        headers = Headers(scope=scope) if scope["type"] == "http" else None
        token = headers.get(CALLS_HEADER) if headers else None
        if headers is None or not token:
            await self.app(scope, receive, send)
            return
        body, replay = await _read_body(receive)
        response = _Response(send)
        who = caller(headers.get("authorization", ""))
        with self.calls.running(who, token) as cancel_scope:
            with cancel_scope:
                await self.app(scope, replay, response.send)
            if cancel_scope.cancelled_caught:
                await response.end_cancelled(scope, receive, _request_id(body))


class _Response:
    """What of the response went out, so a cancelled call can still end it whole."""

    def __init__(self, send: Send) -> None:
        self._send = send
        self.streaming = False
        self.started = False
        self.ended = False

    async def send(self, message: Message) -> None:
        if message["type"] == "http.response.start":
            self.started = True
            content_type = Headers(raw=message.get("headers", [])).get(
                "content-type", ""
            )
            self.streaming = content_type.startswith("text/event-stream")
        elif message["type"] == "http.response.body" and not message.get(
            "more_body", False
        ):
            self.ended = True
        await self._send(message)

    async def end_cancelled(
        self, scope: Scope, receive: Receive, request_id: Any
    ) -> None:
        error = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": REQUEST_CANCELLED, "message": "Request cancelled"},
        }
        if not self.started:
            await JSONResponse(error)(scope, receive, self._send)
        elif not self.ended:
            event = (
                f"event: message\ndata: {json.dumps(error)}\n\n"
                if self.streaming
                else ""
            )
            await self._send(
                {
                    "type": "http.response.body",
                    "body": event.encode(),
                    "more_body": False,
                }
            )


async def _read_body(receive: Receive) -> tuple[bytes, Receive]:
    """The request's body, and a receive that hands it to the server again."""
    body = b""
    while True:
        message = await receive()
        body += message.get("body", b"")
        if not message.get("more_body", False):
            break
    replayed = False

    async def replay() -> Message:
        nonlocal replayed
        if replayed:
            return await receive()
        replayed = True
        return {"type": "http.request", "body": body, "more_body": False}

    return body, replay


def _request_id(body: bytes) -> Any:
    try:
        return json.loads(body).get("id")
    except (ValueError, AttributeError):
        return None
