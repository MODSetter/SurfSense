"""Studio's edit client for the bundled sd-server: its native job route, with the
pictures as reference images, as every edit model sd.cpp documents is run.

Its `/v1/images/edits` and `/sdapi/v1/img2img` also make the picture the
starting noise, which re-draws it at strength 0.75 instead of following the
instruction.
"""

import base64
import io
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

import httpx
from PIL import Image

from modules.llm.providers.picture_shape import Shape, local_dimensions
from modules.llm.providers.protocols import GeneratedImage
from modules.llm.providers.sdcpp.native_job import run_native_job
from modules.llm.providers.sdcpp.serving import wait_until_serving


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
        self,
        model: str,
        prompt: str,
        images: tuple[GeneratedImage, ...],
        *,
        shape: Shape | None = None,
    ) -> GeneratedImage:
        # Held for the whole edit, as for a drawn image (generator.py).
        async with self._give_up_text_runtime():
            await wait_until_serving(
                self._root_url,
                self._served_file,
                interval=self._interval,
                transport=self._transport,
            )
            return await run_native_job(
                self._root_url,
                _body(prompt, images, shape),
                interval=self._interval,
                transport=self._transport,
            )


def _body(prompt: str, images: tuple[GeneratedImage, ...], shape: Shape | None) -> dict:
    # A native request starts from the launch's settings, so steps and guidance
    # are the model's own; the size must be the picture's, or the shape's.
    width, height = Image.open(io.BytesIO(images[0].content)).size
    if shape is not None:
        width, height = local_dimensions(shape, width * height)
    return {
        "prompt": prompt,
        "ref_images": [
            f"data:{image.media_type};base64,{base64.b64encode(image.content).decode()}"
            for image in images
        ],
        "width": width,
        "height": height,
        "output_format": "png",
    }
