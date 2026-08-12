"""Durable object-store helpers for podcast audio (legacy + cutover)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from app.file_storage.factory import get_storage_backend

_AUDIO_CONTENT_TYPE = "audio/mpeg"


def build_audio_key(*, workspace_id: int, podcast_id: int) -> str:
    """Object key: ``podcasts/{workspace_id}/{podcast_id}/{uuid}.mp3``."""
    return f"podcasts/{workspace_id}/{podcast_id}/{uuid.uuid4().hex}.mp3"


async def persist(
    *, workspace_id: int, podcast_id: int, data: bytes
) -> tuple[str, str]:
    """Persist audio bytes; return ``(backend_name, storage_key)``."""
    backend = get_storage_backend()
    key = build_audio_key(workspace_id=workspace_id, podcast_id=podcast_id)
    await backend.put(key, data, content_type=_AUDIO_CONTENT_TYPE)
    return backend.backend_name, key


def open_stream(storage_key: str) -> AsyncIterator[bytes]:
    return get_storage_backend().open_stream(storage_key)


def open_podcast_stream(podcast: Any) -> AsyncIterator[bytes]:
    """Stream a ready podcast's audio. Raises if it has no ``storage_key``."""
    if not podcast.storage_key:
        raise FileNotFoundError(f"podcast {podcast.id} has no stored audio")
    return open_stream(podcast.storage_key)


async def exists(podcast: Any) -> bool:
    return bool(podcast.storage_key) and await get_storage_backend().exists(
        podcast.storage_key
    )


async def purge(podcast: Any) -> None:
    """Delete a podcast's stored audio if present."""
    await purge_key(podcast.storage_key)


async def purge_key(key: str | None) -> None:
    """Delete a stored audio object by key (e.g. superseded on re-render)."""
    if key:
        await get_storage_backend().delete(key)
