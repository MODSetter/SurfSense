"""A remote model given pictures and an instruction: an edit, or a page that keeps
its references. `/images/edits` as OpenAI takes it; `/images` with
`input_references` where a server has no edit route, as OpenRouter."""

import base64
import json

import httpx

from modules.llm.connections.key_headers import key_headers
from modules.llm.providers.openai_compatible.image_response import (
    PICTURE_ITSELF,
    NonRetryableImageError,
    read_image,
    reply_payload,
)
from modules.llm.providers.picture_shape import ASPECT_RATIO, SIZE, Shape
from modules.llm.providers.protocols import GeneratedImage

# An edit reads the picture as well as drawing one: slower than a generation.
TIMEOUT = httpx.Timeout(300.0, connect=5.0)
EDITS = "/images/edits"
REFERENCES = "/images"
# A missing route answers before any work, so trying the other bills nothing.
_NO_ROUTE = {404, 405}

# Optional fields, dropped one at a time when a server refuses them: GPT image
# models refuse `response_format` and take a size, so each is its own.
PICTURE = "response_format"
SHAPE = "shape"
_OPTIONAL = (PICTURE, SHAPE)

# Per server: which route takes pictures, and which optional fields it refuses.
_routes: dict[str, str] = {}
_refused: dict[str, frozenset[str]] = {}


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
        self,
        model: str,
        prompt: str,
        images: tuple[GeneratedImage, ...],
        *,
        shape: Shape | None = None,
    ) -> GeneratedImage:
        route = _routes.get(self._base_url, EDITS)
        refused = _refused.get(self._base_url, frozenset())
        try:
            status, payload = await self._post(
                route, model, prompt, images, shape, refused
            )
            if status in _NO_ROUTE and route == EDITS:
                route = REFERENCES
                status, payload = await self._post(
                    route, model, prompt, images, shape, refused
                )
            # Without each optional field in turn if refused: a 400 comes before any work.
            for field in _OPTIONAL:
                if status != 400 or field in refused:
                    continue
                refused = refused | {field}
                status, payload = await self._post(
                    route, model, prompt, images, shape, refused
                )
            if status >= 400:
                raise NonRetryableImageError(f"image endpoint returned HTTP {status}")
            edited = await read_image(payload)
        except NonRetryableImageError:
            raise
        except (httpx.HTTPError, ValueError, KeyError, json.JSONDecodeError) as error:
            raise NonRetryableImageError(str(error)) from error
        _routes[self._base_url] = route
        _refused[self._base_url] = refused
        return edited

    async def _post(
        self,
        route: str,
        model: str,
        prompt: str,
        images: tuple[GeneratedImage, ...],
        shape: Shape | None,
        refused: frozenset[str],
    ) -> tuple[int, object]:
        async with httpx.AsyncClient(
            timeout=TIMEOUT,
            headers=key_headers(self._base_url, self._api_key),
            transport=self._transport,
        ) as client:
            if route == REFERENCES:
                request = client.stream(
                    "POST",
                    f"{self._base_url}{route}",
                    json=_references_body(model, prompt, images, shape, refused),
                )
            else:
                request = client.stream(
                    "POST",
                    f"{self._base_url}{route}",
                    data=_edits_fields(model, prompt, shape, refused),
                    files=_edits_files(images),
                )
            async with request as reply:
                return reply.status_code, await reply_payload(reply)


def _edits_fields(
    model: str, prompt: str, shape: Shape | None, refused: frozenset[str]
) -> dict[str, str]:
    # No `input_fidelity`: only some GPT image models take it.
    fields = {"model": model, "prompt": prompt}
    if PICTURE not in refused:
        fields.update(PICTURE_ITSELF)
    if shape is not None and SHAPE not in refused:
        fields["size"] = SIZE[shape]
    return fields


def _edits_files(images: tuple[GeneratedImage, ...]) -> list[tuple[str, tuple]]:
    # One picture keeps the field every edit server takes; several are OpenAI's `image[]`.
    field = "image" if len(images) == 1 else "image[]"
    return [
        (field, (f"image-{n}.{_extension(image)}", image.content, image.media_type))
        if len(images) > 1
        else (field, (f"image.{_extension(image)}", image.content, image.media_type))
        for n, image in enumerate(images, 1)
    ]


def _references_body(
    model: str,
    prompt: str,
    images: tuple[GeneratedImage, ...],
    shape: Shape | None,
    refused: frozenset[str],
) -> dict:
    body: dict = {
        "model": model,
        "prompt": prompt,
        "input_references": [
            {"type": "image_url", "image_url": {"url": _data_url(image)}}
            for image in images
        ],
    }
    if shape is not None and SHAPE not in refused:
        body["aspect_ratio"] = ASPECT_RATIO[shape]
    return body


def _data_url(image: GeneratedImage) -> str:
    return f"data:{image.media_type};base64,{base64.b64encode(image.content).decode()}"


def _extension(image: GeneratedImage) -> str:
    return image.media_type.removeprefix("image/").replace("jpeg", "jpg")
