"""A remote edit model, reached on `/images/edits` with one picture and its instruction."""

import json

import httpx

from modules.llm.connections.key_headers import key_headers
from modules.llm.providers.openai_compatible.image_response import (
    MAX_RESPONSE_BYTES,
    PICTURE_ITSELF,
    NonRetryableImageError,
    bounded_body,
    read_image,
)
from modules.llm.providers.protocols import GeneratedImage

# An edit reads the picture as well as drawing one: slower than a generation.
TIMEOUT = httpx.Timeout(300.0, connect=5.0)
ROUTE = "/images/edits"

# Whether an endpoint takes PICTURE_ITSELF; GPT image models refuse it.
_asks_for_picture: dict[str, bool] = {}


class OpenAICompatibleImageEditor:
    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._transport = transport

    async def edit(
        self, model: str, prompt: str, image: GeneratedImage
    ) -> GeneratedImage:
        picture = _asks_for_picture.get(self._base_url, True)
        try:
            status, payload = await self._post(model, prompt, image, picture)
            # Once more without it if refused: a 400 comes before any work.
            if status == 400 and picture:
                picture = False
                status, payload = await self._post(model, prompt, image, picture)
            if status >= 400:
                raise NonRetryableImageError(f"image endpoint returned HTTP {status}")
            edited = await read_image(payload)
        except NonRetryableImageError:
            raise
        except (httpx.HTTPError, ValueError, KeyError, json.JSONDecodeError) as error:
            raise NonRetryableImageError(str(error)) from error
        _asks_for_picture[self._base_url] = picture
        return edited

    async def _post(
        self, model: str, prompt: str, image: GeneratedImage, picture: bool
    ) -> tuple[int, object]:
        extension = image.media_type.removeprefix("image/").replace("jpeg", "jpg")
        # No `input_fidelity`: only some GPT image models take it.
        async with (
            httpx.AsyncClient(
                timeout=TIMEOUT,
                headers=key_headers(self._base_url, self._api_key),
                transport=self._transport,
            ) as client,
            client.stream(
                "POST",
                f"{self._base_url}{ROUTE}",
                data={
                    "model": model,
                    "prompt": prompt,
                    **(PICTURE_ITSELF if picture else {}),
                },
                files={
                    "image": (f"image.{extension}", image.content, image.media_type)
                },
            ) as reply,
        ):
            content = await bounded_body(reply, MAX_RESPONSE_BYTES)
            try:
                payload = json.loads(content)
            except json.JSONDecodeError:
                if reply.status_code >= 400:
                    payload = {}
                else:
                    raise
            return reply.status_code, payload
