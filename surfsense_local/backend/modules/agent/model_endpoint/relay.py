"""The model's reply, handed back to opencode as the model sent it.

The model's own status passes through, so opencode reads its errors as it reads
any provider's. Waiting has no limit here: a local model can take minutes to
load and read the prompt before its first byte, and opencode's configuration
sets how long it waits.
"""

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import anyio
import httpx
from fastapi import Response
from fastapi.responses import StreamingResponse

from modules.agent.model_endpoint.error_replies import as_error_body, error_reply
from modules.agent.model_endpoint.model_address import ModelAddress

# Connecting is the one step with a budget: a runtime that is not running
# refuses at once, and a remote host that cannot be reached should say so.
TIMEOUT = httpx.Timeout(None, connect=10.0)
_DONE = "data: [DONE]"


async def relay(
    address: ModelAddress, body: dict[str, Any], done: Callable[[], Awaitable[None]]
) -> Response:
    """Send `body` to the model and answer with its reply; `done` runs once it is over."""
    client = httpx.AsyncClient(timeout=TIMEOUT)
    try:
        reply = await client.send(
            client.build_request(
                "POST", address.url, json=body, headers=address.headers
            ),
            stream=True,
        )
    except httpx.HTTPError as failure:
        await _close(client, done)
        return error_reply(502, f"the model did not answer: {_reason(failure)}")

    if reply.status_code >= 400 or not body.get("stream"):
        content = await reply.aread()
        await _close(client, done, reply)
        if reply.status_code >= 400:
            content = as_error_body(content, reply.status_code)
        return Response(
            content,
            status_code=reply.status_code,
            media_type=reply.headers.get("content-type", "application/json"),
        )

    return StreamingResponse(
        _frames(client, reply, done),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _frames(
    client: httpx.AsyncClient,
    reply: httpx.Response,
    done: Callable[[], Awaitable[None]],
) -> AsyncIterator[bytes]:
    """The model's SSE lines as they arrive, always closed by `[DONE]`."""
    ended = False
    try:
        async for line in reply.aiter_lines():
            ended = ended or line.strip() == _DONE
            yield f"{line}\n".encode()
    except httpx.HTTPError as failure:
        error = {
            "error": {"message": f"the model stopped answering: {_reason(failure)}"}
        }
        yield f"data: {json.dumps(error)}\n\n".encode()
    finally:
        # Starlette cancels this on a disconnect; the model must still be released.
        with anyio.CancelScope(shield=True):
            await _close(client, done, reply)
    if not ended:
        yield f"{_DONE}\n\n".encode()


async def _close(
    client: httpx.AsyncClient,
    done: Callable[[], Awaitable[None]],
    reply: httpx.Response | None = None,
) -> None:
    """Release the connection and the model, whichever way the turn ended."""
    if reply is not None:
        await reply.aclose()
    await client.aclose()
    await done()


def _reason(failure: httpx.HTTPError) -> str:
    """What went wrong on the way to the model, in a few words."""
    return str(failure) or type(failure).__name__
