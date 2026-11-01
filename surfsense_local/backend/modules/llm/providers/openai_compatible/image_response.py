"""Reading the `data[]` an image endpoint answers with, for drawing and editing alike."""

import base64
import binascii
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

import httpx

from modules.llm.providers.protocols import GeneratedImage

DOWNLOAD_TIMEOUT = httpx.Timeout(180.0, connect=5.0)
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_RESPONSE_BYTES = 28 * 1024 * 1024
MAX_REDIRECTS = 3


class NonRetryableImageError(RuntimeError):
    """An image request began, so repeating it could duplicate a billed result."""


# Raises to refuse a host the endpoint named for its image. The caller owns the
# egress decision, so this provider never needs the database.
AllowUrlHost = Callable[[str], Awaitable[None]]


async def read_image(payload: object, allow_url_host: AllowUrlHost) -> GeneratedImage:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError("image endpoint returned no data list")
    entry = next((item for item in payload["data"] if isinstance(item, dict)), None)
    if entry is None:
        raise ValueError("image endpoint returned no image")

    media_type = entry.get("media_type")
    if not isinstance(media_type, str):
        media_type = None
    encoded = entry.get("b64_json")
    if isinstance(encoded, str):
        return decode_image(encoded, media_type)

    url = entry.get("url")
    if not isinstance(url, str):
        raise ValueError("image endpoint returned neither b64_json nor url")
    if url.startswith("data:"):
        return _decode_data_url(url)
    await allow_url_host(url)
    return await download_image(url, allow_url_host)


async def bounded_body(reply: httpx.Response, limit: int) -> bytes:
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
    return decode_image(encoded, media_type)


def decode_image(encoded: str, media_type: str | None) -> GeneratedImage:
    try:
        content = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("image response contains invalid base64") from error
    if not content or len(content) > MAX_IMAGE_BYTES:
        raise ValueError("generated image is empty or too large")
    return GeneratedImage(content, _validated_media_type(content, media_type))


async def download_image(
    url: str,
    allow_url_host: AllowUrlHost,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> GeneratedImage:
    """The image at `url`, which the caller has allowed. Redirects are followed
    by hand, so each host they name passes egress before it is asked."""
    _require_plain_http(url)
    # Never forward the model endpoint's bearer token to a returned URL.
    async with httpx.AsyncClient(
        timeout=DOWNLOAD_TIMEOUT, transport=transport
    ) as client:
        for hop in range(MAX_REDIRECTS + 1):
            async with client.stream("GET", url) as reply:
                if not reply.is_redirect:
                    reply.raise_for_status()
                    content = await bounded_body(reply, MAX_IMAGE_BYTES)
                    media_type = reply.headers.get("content-type", "")
                    media_type = media_type.split(";", 1)[0]
                    break
                # Before the check: a refused host is recorded for Settings.
                if hop == MAX_REDIRECTS:
                    raise ValueError("generated image URL redirected too many times")
                url = str(reply.url.join(reply.headers["location"]))
            _require_plain_http(url)
            await allow_url_host(url)
    if not content:
        raise ValueError("generated image download was empty")
    return GeneratedImage(content, _validated_media_type(content, media_type))


def _require_plain_http(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("generated image URL must be HTTP(S)")
    if parsed.username or parsed.password:
        raise ValueError("generated image URL must not contain credentials")


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
