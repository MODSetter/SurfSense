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

__all__ = ["NonRetryableImageError", "OpenAICompatibleImageProvider"]

TIMEOUT = httpx.Timeout(180.0, connect=5.0)
STANDARD_ROUTE = "/images/generations"
EXTENSION_ROUTE = "/images"

_route_cache: dict[tuple[int, str], str] = {}
# Whether an endpoint takes PICTURE_ITSELF; GPT image models refuse it.
_asks_for_picture: dict[tuple[int, str], bool] = {}


class OpenAICompatibleImageProvider:
    def __init__(
        self,
        connection_id: int,
        base_url: str,
        api_key: str | None = None,
    ) -> None:
        self._connection_id = connection_id
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    def _headers(self) -> dict[str, str]:
        return key_headers(self._base_url, self._api_key)

    async def generate(self, model: str, prompt: str) -> GeneratedImage:
        key = (self._connection_id, self._base_url)
        preferred = _route_cache.get(key, STANDARD_ROUTE)
        alternate = EXTENSION_ROUTE if preferred == STANDARD_ROUTE else STANDARD_ROUTE

        picture = _asks_for_picture.get(key, True)

        try:
            status, payload, picture = await self._ask(
                preferred, model, prompt, picture
            )
            if status in {404, 405}:
                status, payload, picture = await self._ask(
                    alternate, model, prompt, picture
                )
                route = alternate
            else:
                route = preferred
            if status >= 400:
                raise NonRetryableImageError(f"image endpoint returned HTTP {status}")
            image = await read_image(payload)
        except NonRetryableImageError:
            raise
        except (httpx.HTTPError, ValueError, KeyError, json.JSONDecodeError) as error:
            raise NonRetryableImageError(str(error)) from error

        _route_cache[key] = route
        _asks_for_picture[key] = picture
        return image

    async def _ask(
        self, route: str, model: str, prompt: str, picture: bool
    ) -> tuple[int, object, bool]:
        """Once more without PICTURE_ITSELF if it is refused: a 400 comes before
        any work, so nothing is billed twice."""
        status, payload = await self._post(route, model, prompt, picture)
        if status == 400 and picture:
            status, payload = await self._post(route, model, prompt, False)
            picture = False
        return status, payload, picture

    async def _post(
        self, route: str, model: str, prompt: str, picture: bool
    ) -> tuple[int, object]:
        async with (
            httpx.AsyncClient(timeout=TIMEOUT, headers=self._headers()) as client,
            client.stream(
                "POST",
                f"{self._base_url}{route}",
                json={
                    "model": model,
                    "prompt": prompt,
                    **(PICTURE_ITSELF if picture else {}),
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
