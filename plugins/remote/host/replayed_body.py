"""A request's body read before the server sees it, then handed to the server again."""

from starlette.types import Message, Receive


async def read_body(receive: Receive) -> tuple[bytes, Receive]:
    """The request's whole body, and a receive that hands it to the server again."""
    body, _, replay = await _read(receive, None)
    return body, replay


async def read_body_up_to(receive: Receive, limit: int) -> tuple[bytes | None, Receive]:
    """The body if it is no longer than `limit`, else None; the server still gets all of it.

    For a read before the license check, so an unlicensed caller cannot make the
    host hold an unbounded body.
    """
    body, whole, replay = await _read(receive, limit)
    return (body if whole else None), replay


async def _read(receive: Receive, limit: int | None) -> tuple[bytes, bool, Receive]:
    body = b""
    more = True
    while more and (limit is None or len(body) <= limit):
        message = await receive()
        body += message.get("body", b"")
        more = message.get("more_body", False)
    replayed = False

    async def replay() -> Message:
        nonlocal replayed
        if replayed:
            return await receive()
        replayed = True
        return {"type": "http.request", "body": body, "more_body": more}

    return body, not more, replay
