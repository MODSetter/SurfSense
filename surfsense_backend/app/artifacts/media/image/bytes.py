"""Decode the bytes of a provider image response.

Shared by the persistence path (``record``) and the no-persist public door,
so both agree on how a litellm image response turns into raw bytes.
"""

from __future__ import annotations

import base64
from typing import Any

import httpx

PROVIDER_FETCH_TIMEOUT_SECONDS = 30


def _image_type(data: bytes) -> tuple[str, str]:
    """Return ``(extension, mime_type)`` sniffed from the leading bytes."""
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg", "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp", "image/webp"
    return "png", "image/png"


async def _bytes_from(entry: dict[str, Any]) -> bytes:
    """Decode the inline payload, or download the provider's temporary URL.

    Those URLs expire within the hour, so the bytes must be pulled now.
    """
    b64 = entry.get("b64_json")
    if b64:
        return base64.b64decode(b64)

    url = entry.get("url")
    if not url:
        raise ValueError("image response carried neither b64_json nor url")

    async with httpx.AsyncClient(timeout=PROVIDER_FETCH_TIMEOUT_SECONDS) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


async def image_bytes_from_response(response: dict[str, Any]) -> tuple[bytes, str, str]:
    """Resolve the first image of a provider response to ``(data, mime, ext)``."""
    images = response.get("data")
    if not isinstance(images, list) or not images or not isinstance(images[0], dict):
        raise ValueError("image response carried no data entries")

    data = await _bytes_from(images[0])
    if not data:
        raise ValueError("image response resolved to empty bytes")

    extension, mime_type = _image_type(data)
    return data, mime_type, extension
