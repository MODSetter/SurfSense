"""Studio's edit client for the bundled sd-server: its native job route, with the
picture as a reference image, as every edit model sd.cpp documents is run.

Its `/v1/images/edits` and `/sdapi/v1/img2img` also make the picture the
starting noise, which re-draws it at strength 0.75 instead of following the
instruction.
"""

import asyncio
import base64
import contextlib
import io
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager

import httpx
from PIL import Image

from modules.llm.providers.openai_compatible.image_response import (
    NonRetryableImageError,
    decode_image,
)
from modules.llm.providers.protocols import GeneratedImage
from modules.llm.providers.sdcpp.serving import wait_until_serving
from shared import cancellation

_TIMEOUT = httpx.Timeout(30.0, connect=5.0)
# A finished job's result is kept 600 seconds, so a poll each second meets it.
_ENDED = ("completed", "failed", "cancelled")


class LocalImageEditor:
    def __init__(
        self,
        root_url: str,
        served_file: str,
        give_up_text_runtime: Callable[[], AbstractAsyncContextManager[None]],
        *,
        interval: float = 1.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._root_url = root_url
        self._served_file = served_file
        self._give_up_text_runtime = give_up_text_runtime
        self._interval = interval
        self._transport = transport

    async def edit(
        self, model: str, prompt: str, image: GeneratedImage
    ) -> GeneratedImage:
        # Held for the whole edit, as for a drawn image (generator.py).
        async with self._give_up_text_runtime():
            await wait_until_serving(
                self._root_url,
                self._served_file,
                interval=self._interval,
                transport=self._transport,
            )
            async with httpx.AsyncClient(
                base_url=self._root_url, timeout=_TIMEOUT, transport=self._transport
            ) as client:
                job = await self._submit(client, prompt, image)
                try:
                    return await self._result(client, job)
                except BaseException:
                    # Only a queued job can be withdrawn; a generating one runs on
                    # until Electron stops sd-server, once the cancel ends its demand.
                    await _withdraw(client, job)
                    raise

    async def _submit(
        self, client: httpx.AsyncClient, prompt: str, image: GeneratedImage
    ) -> str:
        width, height = Image.open(io.BytesIO(image.content)).size
        encoded = base64.b64encode(image.content).decode()
        # A native request starts from the launch's settings, so steps and
        # guidance are the model's own; the size must be the picture's.
        body = {
            "prompt": prompt,
            "ref_images": [f"data:{image.media_type};base64,{encoded}"],
            "width": width,
            "height": height,
            "output_format": "png",
        }
        reply = await _call(client.post("/sdcpp/v1/img_gen", json=body))
        return reply.json()["id"]

    async def _result(self, client: httpx.AsyncClient, job: str) -> GeneratedImage:
        while True:
            cancellation.raise_if_cancelled()
            state = (await _call(client.get(f"/sdcpp/v1/jobs/{job}"))).json()
            if state["status"] == "completed":
                return decode_image(state["result"]["images"][0]["b64_json"], None)
            if state["status"] in _ENDED:
                error = state.get("error") or {}
                raise NonRetryableImageError(
                    f"The image model could not edit this picture: "
                    f"{error.get('message') or state['status']}"
                )
            await asyncio.sleep(self._interval)


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
