"""How a tools/call ended, read from the response the host sent back."""

import json
from typing import Any

import anyio
from starlette.datastructures import Headers
from starlette.types import Message

from host.cancellable_calls import REQUEST_CANCELLED

OK = "ok"
TOOL_ERROR = "tool_error"
REFUSED = "refused"
CANCELLED = "cancelled"
ERROR = "error"


class CallOutcome:
    """Each response message is shown to it after it is sent; it keeps only the verdict.

    The answer is the JSON-RPC response with the request's id, as one JSON body or one
    event in a stream; progress notifications on the way are skipped.
    """

    def __init__(self, request_id: Any) -> None:
        self._request_id = request_id
        self._status: int | None = None
        self._streaming = False
        self._unread = b""
        self._answer: str | None = None

    def saw(self, message: Message) -> None:
        if self._answer is not None:
            return
        if message["type"] == "http.response.start":
            self._status = message["status"]
            content_type = Headers(raw=message.get("headers", [])).get(
                "content-type", ""
            )
            self._streaming = content_type.startswith("text/event-stream")
        elif message["type"] == "http.response.body" and self._status == 200:
            self._unread += message.get("body", b"")
            if self._streaming:
                self._read_events()
            elif not message.get("more_body", False):
                self._read_answer(self._unread)
                self._unread = b""

    def outcome(self, refused: bool, raised: BaseException | None) -> str:
        if refused:
            return REFUSED
        if self._answer is not None:
            return self._answer
        if isinstance(raised, anyio.get_cancelled_exc_class()):
            return CANCELLED
        return ERROR

    def _read_events(self) -> None:
        # The SDK ends its lines with CRLF, the host's own cancelled answer with LF.
        self._unread = self._unread.replace(b"\r\n", b"\n")
        while self._answer is None and b"\n\n" in self._unread:
            event, self._unread = self._unread.split(b"\n\n", 1)
            data = [
                line[5:].removeprefix(b" ")
                for line in event.split(b"\n")
                if line.startswith(b"data:")
            ]
            if data:
                self._read_answer(b"\n".join(data))
        if self._answer is not None:
            self._unread = b""

    def _read_answer(self, data: bytes) -> None:
        try:
            message = json.loads(data)
        except ValueError:
            return
        if (
            not isinstance(message, dict)
            or "method" in message
            or message.get("id") != self._request_id
        ):
            return
        error, result = message.get("error"), message.get("result")
        if isinstance(error, dict):
            cancelled = error.get("code") == REQUEST_CANCELLED
            self._answer = CANCELLED if cancelled else ERROR
        elif isinstance(result, dict):
            self._answer = TOOL_ERROR if result.get("isError") else OK
