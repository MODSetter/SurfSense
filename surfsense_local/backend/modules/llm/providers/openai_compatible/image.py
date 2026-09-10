import base64
import binascii
import json
from urllib.parse import urlsplit

import httpx

from modules.llm.providers.protocols import GeneratedImage

TIMEOUT = httpx.Timeout(180.0, connect=5.0)
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_RESPONSE_BYTES = 28 * 1024 * 1024
STANDARD_ROUTE = "/images/generations"
EXTENSION_ROUTE = "/images"

_route_cache: dict[tuple[int, str], str] = {}


class NonRetryableImageError(RuntimeError):
    """An image request began, so repeating it could duplicate a billed result."""


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
        return (
            {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        )

    async def generate(self, model: str, prompt: str) -> GeneratedImage:
        key = (self._connection_id, self._base_url)
        preferred = _route_cache.get(key, STANDARD_ROUTE)
        alternate = (
            EXTENSION_ROUTE if preferred == STANDARD_ROUTE else STANDARD_ROUTE
        )

        try:
            status, payload = await self._post(preferred, model, prompt)
            if status in {404, 405}:
                status, payload = await self._post(alternate, model, prompt)
                route = alternate
            else:
                route = preferred
            if status >= 400:
                raise NonRetryableImageError(
                    f"image endpoint returned HTTP {status}"
                )
            image = await self._normalize(payload)
        except NonRetryableImageError:
            raise
        except (httpx.HTTPError, ValueError, KeyError, json.JSONDecodeError) as error:
            raise NonRetryableImageError(str(error)) from error

        _route_cache[key] = route
        return image

    async def _post(
        self, route: str, model: str, prompt: str
    ) -> tuple[int, object]:
        async with (
            httpx.AsyncClient(timeout=TIMEOUT, headers=self._headers()) as client,
            client.stream(
                "POST",
                f"{self._base_url}{route}",
                json={"model": model, "prompt": prompt},
            ) as reply,
        ):
            content = await _bounded_body(reply, MAX_RESPONSE_BYTES)
            try:
                payload = json.loads(content)
            except json.JSONDecodeError:
                if reply.status_code >= 400:
                    payload = {}
                else:
                    raise
            return reply.status_code, payload

    async def _normalize(self, payload: object) -> GeneratedImage:
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise ValueError("image endpoint returned no data list")
        entry = next(
            (item for item in payload["data"] if isinstance(item, dict)), None
        )
        if entry is None:
            raise ValueError("image endpoint returned no image")

        media_type = entry.get("media_type")
        if not isinstance(media_type, str):
            media_type = None
        encoded = entry.get("b64_json")
        if isinstance(encoded, str):
            return _decode_image(encoded, media_type)

        url = entry.get("url")
        if not isinstance(url, str):
            raise ValueError("image endpoint returned neither b64_json nor url")
        if url.startswith("data:"):
            return _decode_data_url(url)
        return await _download_image(url)


async def _bounded_body(reply: httpx.Response, limit: int) -> bytes:
    length = reply.headers.get("content-length")
    if length is not None and length.isdigit() and int(length) > limit:
        raise ValueError("image response is too large")
    chunks: list[bytes] = []
    size = 0
    async for chunk in reply.aiter_bytes():
        size += len(chunk)
        if size > limit:
            raise ValueError("image response is too large")
        chunks.append(chunk)
    return b"".join(chunks)


def _decode_data_url(url: str) -> GeneratedImage:
    header, separator, encoded = url.partition(",")
    if not separator or ";base64" not in header:
        raise ValueError("image data URL must be base64 encoded")
    media_type = header.removeprefix("data:").split(";", 1)[0] or None
    return _decode_image(encoded, media_type)


def _decode_image(encoded: str, media_type: str | None) -> GeneratedImage:
    try:
        content = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("image response contains invalid base64") from error
    if not content or len(content) > MAX_IMAGE_BYTES:
        raise ValueError("generated image is empty or too large")
    return GeneratedImage(content, _validated_media_type(content, media_type))


async def _download_image(url: str) -> GeneratedImage:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("generated image URL must be HTTP(S)")
    if parsed.username or parsed.password:
        raise ValueError("generated image URL must not contain credentials")

    # Never forward the model endpoint's bearer token to a returned URL.
    async with (
        httpx.AsyncClient(
            timeout=TIMEOUT, follow_redirects=True, max_redirects=3
        ) as client,
        client.stream("GET", url) as reply,
    ):
        reply.raise_for_status()
        content = await _bounded_body(reply, MAX_IMAGE_BYTES)
        media_type = reply.headers.get("content-type", "").split(";", 1)[0]
    if not content:
        raise ValueError("generated image download was empty")
    return GeneratedImage(content, _validated_media_type(content, media_type))


def _validated_media_type(content: bytes, claimed: str | None) -> str:
    detected: str | None = None
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        detected = "image/png"
    elif content.startswith(b"\xff\xd8\xff"):
        detected = "image/jpeg"
    elif content.startswith((b"GIF87a", b"GIF89a")):
        detected = "image/gif"
    elif content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        detected = "image/webp"
    else:
        prefix = content[:512].lstrip()
        if prefix.startswith(b"<svg") or (
            prefix.startswith(b"<?xml") and b"<svg" in prefix
        ):
            detected = "image/svg+xml"
    if detected is None:
        raise ValueError("generated bytes are not a supported image")
    if claimed and claimed != detected:
        raise ValueError("generated image MIME type does not match its bytes")
    return detected
