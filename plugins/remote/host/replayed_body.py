"""A request's body read whole before the server sees it, then handed to the server again."""

from starlette.types import Message, Receive


async def read_body(receive: Receive) -> tuple[bytes, Receive]:
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
