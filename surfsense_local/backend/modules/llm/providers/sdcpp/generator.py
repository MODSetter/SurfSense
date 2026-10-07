"""Studio's image client for the bundled sd-server: the OpenAI-compatible one,
once sd-server serves the model the job needs and the text runtime has given up
the graphics card."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

import httpx

from modules.llm.providers.protocols import GeneratedImage, ImageGenerator
from modules.llm.providers.sdcpp.serving import wait_until_serving


class LocalImageGenerator:
    def __init__(
        self,
        inner: ImageGenerator,
        root_url: str,
        served_file: str,
        give_up_text_runtime: Callable[[], AbstractAsyncContextManager[None]],
        *,
        interval: float = 1.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._inner = inner
        self._root_url = root_url
        self._served_file = served_file
        self._give_up_text_runtime = give_up_text_runtime
        self._interval = interval
        self._transport = transport

    async def generate(self, model: str, prompt: str) -> GeneratedImage:
        # sd-server loads its weights on this post, and Windows reports the card
        # as free while llama-server holds it. Held for the whole image, so a
        # chat sent meanwhile cannot load a text model back under it.
        async with self._give_up_text_runtime():
            await wait_until_serving(
                self._root_url,
                self._served_file,
                interval=self._interval,
                transport=self._transport,
            )
            return await self._inner.generate(model, prompt)
