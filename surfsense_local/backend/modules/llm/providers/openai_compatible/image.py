import json

import httpx

from modules.llm.connections.key_headers import key_headers
from modules.llm.providers.openai_compatible.image_response import (
    PICTURE_ITSELF,
    NonRetryableImageError,
    read_image,
    reply_payload,
)
from modules.llm.providers.picture_shape import ASPECT_RATIO, SHAPES, SIZE, Shape
from modules.llm.providers.protocols import GeneratedImage

__all__ = ["NonRetryableImageError", "OpenAICompatibleImageProvider"]

TIMEOUT = httpx.Timeout(180.0, connect=5.0)
STANDARD_ROUTE = "/images/generations"
EXTENSION_ROUTE = "/images"

_route_cache: dict[tuple[int, str], str] = {}
# Whether an endpoint takes PICTURE_ITSELF; GPT image models refuse it.
_asks_for_picture: dict[tuple[int, str], bool] = {}
# Endpoints that refuse a size: they draw their own.
_refuses_size: set[tuple[int, str]] = set()
# OpenRouter's /images names a shape by its ratio, as it does for references.
_RATIO_OF_SIZE = {SIZE[shape]: ASPECT_RATIO[shape] for shape in SHAPES}


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

    async def generate(
        self, model: str, prompt: str, *, shape: Shape | None = None
    ) -> GeneratedImage:
        key = (self._connection_id, self._base_url)
        size = None if shape is None or key in _refuses_size else SIZE[shape]
        preferred = _route_cache.get(key, STANDARD_ROUTE)
        alternate = EXTENSION_ROUTE if preferred == STANDARD_ROUTE else STANDARD_ROUTE

        picture = _asks_for_picture.get(key, True)

        try:
            status, payload, picture, size = await self._ask(
                preferred, model, prompt, picture, size
            )
            if status in {404, 405}:
                status, payload, picture, size = await self._ask(
                    alternate, model, prompt, picture, size
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
        if shape is not None and size is None:
            _refuses_size.add(key)
        return image

    async def _ask(
        self, route: str, model: str, prompt: str, picture: bool, size: str | None
    ) -> tuple[int, object, bool, str | None]:
        """Once more without PICTURE_ITSELF, then without the size, each if it is
        refused: a 400 comes before any work, so nothing is billed twice."""
        status, payload = await self._sent(route, model, prompt, picture, size)
        if status == 400 and picture:
            picture = False
            status, payload = await self._sent(route, model, prompt, picture, size)
        if status == 400 and size is not None:
            size = None
            status, payload = await self._sent(route, model, prompt, picture, size)
        return status, payload, picture, size

    async def _sent(
        self, route: str, model: str, prompt: str, picture: bool, size: str | None
    ) -> tuple[int, object]:
        if size is None:
            return await self._post(route, model, prompt, picture)
        return await self._post(route, model, prompt, picture, size=size)

    async def _post(
        self,
        route: str,
        model: str,
        prompt: str,
        picture: bool,
        size: str | None = None,
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
                    **(_shape_field(route, size) if size else {}),
                },
            ) as reply,
        ):
            return reply.status_code, await reply_payload(reply)


def _shape_field(route: str, size: str) -> dict[str, str]:
    if route == EXTENSION_ROUTE:
        return {"aspect_ratio": _RATIO_OF_SIZE[size]}
    return {"size": size}
