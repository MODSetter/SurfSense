"""The model's reply, handed back to opencode as the model sent it.

The model's own status passes through, so opencode reads its errors as it reads
any provider's. Waiting has no limit here: a local model can take minutes to
load and read the prompt before its first byte, and opencode's configuration
sets how long it waits.
"""

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
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

# Fresh headers after the model refused the ones sent, or None to pass the refusal on.
Reauthorize = Callable[[], Awaitable[dict[str, str]]]
# A refusal before the stream, as the status and body opencode is to read.
Refusal = Callable[[int, bytes], tuple[int, bytes]]


@dataclass(frozen=True)
class Wire:
    """How a route's stream ends and says it broke, as opencode's provider for it reads."""

    # The closing line the model may leave out, or None when the route has none.
    done: str | None
    failure: Callable[[str], dict[str, Any]]


CHAT_COMPLETIONS = Wire(_DONE, lambda message: {"error": {"message": message}})
# A Responses stream ends on its own `response.completed`; a break is an `error` event.
RESPONSES = Wire(
    None, lambda message: {"type": "error", "sequence_number": 0, "message": message}
)


def _passed_on(status: int, content: bytes) -> tuple[int, bytes]:
    return status, as_error_body(content, status)


async def relay(
    address: ModelAddress,
    body: dict[str, Any],
    done: Callable[[], Awaitable[None]],
    *,
    wire: Wire = CHAT_COMPLETIONS,
    reauthorize: Reauthorize | None = None,
    refusal: Refusal = _passed_on,
) -> Response:
    """Send `body` to the model and answer with its reply; `done` runs once it is over."""
    client = httpx.AsyncClient(timeout=TIMEOUT)
    try:
        reply = await _send(client, address.url, body, address.headers)
        if reply.status_code == 401 and reauthorize is not None:
            await reply.aclose()
            reply = await _send(client, address.url, body, await reauthorize())
    except httpx.HTTPError as failure:
        await _close(client, done)
        return error_reply(502, f"the model did not answer: {_reason(failure)}")
    except BaseException:
        await _close(client, done)
        raise

    if reply.status_code >= 400 or not body.get("stream"):
        content = await reply.aread()
        await _close(client, done, reply)
        if reply.status_code >= 400:
            # Always JSON once refused: the body is an `{"error": …}` object.
            status, content = refusal(reply.status_code, content)
            return Response(content, status_code=status, media_type="application/json")
        return Response(
            content,
            status_code=reply.status_code,
            media_type=reply.headers.get("content-type", "application/json"),
        )

    return StreamingResponse(
        _frames(client, reply, done, wire),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _send(
    client: httpx.AsyncClient, url: str, body: dict[str, Any], headers: dict[str, str]
) -> httpx.Response:
    return await client.send(
        client.build_request("POST", url, json=body, headers=headers), stream=True
    )


async def _frames(
    client: httpx.AsyncClient,
    reply: httpx.Response,
    done: Callable[[], Awaitable[None]],
    wire: Wire,
) -> AsyncIterator[bytes]:
    """The model's SSE lines as they arrive, closed by the route's own last line."""
    ended = wire.done is None
    try:
        async for line in reply.aiter_lines():
            ended = ended or line.strip() == wire.done
            yield f"{line}\n".encode()
    except httpx.HTTPError as failure:
        error = wire.failure(f"the model stopped answering: {_reason(failure)}")
        yield f"data: {json.dumps(error)}\n\n".encode()
    finally:
        # Starlette cancels this on a disconnect; the model must still be released.
        with anyio.CancelScope(shield=True):
            await _close(client, done, reply)
    if not ended:
        yield f"{wire.done}\n\n".encode()


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
