"""Offload image-generation b64 payloads into object storage."""

from __future__ import annotations

import base64
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from app.file_storage.factory import get_storage_backend

logger = logging.getLogger(__name__)


def build_image_key(*, workspace_id: int, image_gen_id: int, index: int) -> str:
    return (
        f"images/{workspace_id}/{image_gen_id}/"
        f"{index}-{uuid.uuid4().hex}.bin"
    )


async def offload_b64(
    response_data: dict[str, Any],
    *,
    workspace_id: int,
    image_gen_id: int,
) -> dict[str, Any]:
    """Move ``b64_json`` into object store; drop b64 from the dict."""
    images = response_data.get("data")
    if not isinstance(images, list):
        return response_data

    backend = get_storage_backend()
    for index, entry in enumerate(images):
        if not isinstance(entry, dict):
            continue
        b64 = entry.get("b64_json")
        if not b64:
            continue
        try:
            data = base64.b64decode(b64)
        except Exception:
            logger.warning("Invalid b64_json at image index %s", index, exc_info=True)
            continue
        key = build_image_key(
            workspace_id=workspace_id, image_gen_id=image_gen_id, index=index
        )
        await backend.put(key, data, content_type="image/png")
        entry["storage_backend"] = backend.backend_name
        entry["storage_key"] = key
        entry.pop("b64_json", None)

    return response_data


def open_stream(storage_key: str) -> AsyncIterator[bytes]:
    return get_storage_backend().open_stream(storage_key)


async def purge(response_data: dict[str, Any] | None) -> None:
    if not response_data:
        return
    images = response_data.get("data")
    if not isinstance(images, list):
        return
    backend = get_storage_backend()
    for entry in images:
        if isinstance(entry, dict) and entry.get("storage_key"):
            await backend.delete(entry["storage_key"])
