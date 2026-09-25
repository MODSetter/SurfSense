"""Studio's image client for the bundled sd-server: the OpenAI-compatible one,
once sd-server serves the model the job needs."""

import httpx

from modules.llm.providers.protocols import GeneratedImage, ImageGenerator
from modules.llm.providers.sdcpp.serving import wait_until_serving


class LocalImageGenerator:
    def __init__(
        self,
        inner: ImageGenerator,
        root_url: str,
        served_file: str,
        *,
        interval: float = 1.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._inner = inner
        self._root_url = root_url
        self._served_file = served_file
        self._interval = interval
        self._transport = transport

    async def generate(self, model: str, prompt: str) -> GeneratedImage:
        await wait_until_serving(
            self._root_url,
            self._served_file,
            interval=self._interval,
            transport=self._transport,
        )
        return await self._inner.generate(model, prompt)
