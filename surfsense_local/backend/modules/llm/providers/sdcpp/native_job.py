"""One picture through sd-server's native job route: submit, poll each second,
and withdraw it if the wait ends early. The only route that takes reference
images and a size per request, so both drawing and editing use it."""

import asyncio
import contextlib
from collections.abc import Awaitable

import httpx

from modules.llm.providers.openai_compatible.image_response import (
    NonRetryableImageError,
    decode_image,
)
from modules.llm.providers.protocols import GeneratedImage
from shared import cancellation

_TIMEOUT = httpx.Timeout(30.0, connect=5.0)
# A finished job's result is kept 600 seconds, so a poll each second meets it.
_ENDED = ("completed", "failed", "cancelled")


async def run_native_job(
    root_url: str,
    body: dict,
    *,
    interval: float,
    transport: httpx.AsyncBaseTransport | None,
) -> GeneratedImage:
    async with httpx.AsyncClient(
        base_url=root_url, timeout=_TIMEOUT, transport=transport
    ) as client:
        reply = await _call(client.post("/sdcpp/v1/img_gen", json=body))
        job = reply.json()["id"]
        try:
            return await _result(client, job, interval)
        except BaseException:
            # Only a queued job can be withdrawn; a generating one runs on
            # until Electron stops sd-server, once the cancel ends its demand.
            await _withdraw(client, job)
            raise


async def _result(
    client: httpx.AsyncClient, job: str, interval: float
) -> GeneratedImage:
    while True:
        cancellation.raise_if_cancelled()
        state = (await _call(client.get(f"/sdcpp/v1/jobs/{job}"))).json()
        if state["status"] == "completed":
            return decode_image(state["result"]["images"][0]["b64_json"], None)
        if state["status"] in _ENDED:
            error = state.get("error") or {}
            raise NonRetryableImageError(
                f"The image model could not make this picture: "
                f"{error.get('message') or state['status']}"
            )
        await asyncio.sleep(interval)


async def _call(request: Awaitable[httpx.Response]) -> httpx.Response:
    """The reply, or the edit's failure: a full queue, a job gone, a server down."""
    try:
        reply = await request
    except httpx.HTTPError as error:
        raise NonRetryableImageError(
            f"The image model could not be reached: {error}"
        ) from error
    if reply.status_code >= 400:
        raise NonRetryableImageError(f"sd-server returned HTTP {reply.status_code}")
    return reply


# The text runtime is still held while it is asked; a cancel ends the demand
# anyway, and Electron then stops sd-server.
_WITHDRAW_TIMEOUT = httpx.Timeout(2.0)


async def _withdraw(client: httpx.AsyncClient, job: str) -> None:
    with contextlib.suppress(httpx.HTTPError):
        await client.post(f"/sdcpp/v1/jobs/{job}/cancel", timeout=_WITHDRAW_TIMEOUT)
