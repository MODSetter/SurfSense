"""Durable storage for rendered podcast audio.

Wraps the shared :class:`StorageBackend` so the rest of the module never deals
with object keys directly. Audio is stored under a per-podcast key, streamed for
download, and purged when a podcast is deleted.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from app.file_storage.factory import get_storage_backend
from app.podcasts.persistence import Podcast

_AUDIO_CONTENT_TYPE = "audio/mpeg"


def build_audio_key(*, search_space_id: int, podcast_id: int) -> str:
    """Object key for a podcast's audio.

    Shape: ``podcasts/{search_space_id}/{podcast_id}/{uuid}.mp3``. The uuid lets
    a re-render write a fresh object before the old one is purged.
    """
    return f"podcasts/{search_space_id}/{podcast_id}/{uuid.uuid4().hex}.mp3"


async def store_audio(
    *, search_space_id: int, podcast_id: int, data: bytes
) -> tuple[str, str]:
    """Persist audio bytes and return ``(backend_name, storage_key)``."""
    backend = get_storage_backend()
    key = build_audio_key(search_space_id=search_space_id, podcast_id=podcast_id)
    await backend.put(key, data, content_type=_AUDIO_CONTENT_TYPE)
    return backend.backend_name, key


def open_audio_stream(podcast: Podcast) -> AsyncIterator[bytes]:
    """Stream a ready podcast's audio bytes. Raises if it has none."""
    if not podcast.storage_key:
        raise FileNotFoundError(f"podcast {podcast.id} has no stored audio")
    return get_storage_backend().open_stream(podcast.storage_key)


async def purge_audio(podcast: Podcast) -> None:
    """Delete a podcast's stored audio if present; a missing object is fine."""
    if podcast.storage_key:
        await get_storage_backend().delete(podcast.storage_key)
