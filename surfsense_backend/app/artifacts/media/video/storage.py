"""Offload video-presentation slide audio into object storage."""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from app.file_storage.factory import get_storage_backend

logger = logging.getLogger(__name__)


def build_slide_audio_key(
    *,
    workspace_id: int,
    video_presentation_id: int,
    slide_number: int,
    ext: str,
) -> str:
    suffix = ext.lstrip(".") or "mp3"
    return (
        f"video_presentations/{workspace_id}/{video_presentation_id}/"
        f"slide-{slide_number}-{uuid.uuid4().hex}.{suffix}"
    )


async def offload_slide_audio(
    slides: list[dict[str, Any]],
    *,
    workspace_id: int,
    video_presentation_id: int,
) -> list[dict[str, Any]]:
    """Upload local ``audio_file`` paths; store keys; remove local files."""
    backend = get_storage_backend()
    for slide in slides:
        local_path = slide.get("audio_file")
        if not local_path or not os.path.isfile(local_path):
            continue
        slide_number = int(slide.get("slide_number") or 0)
        try:
            path = Path(local_path)
            data = path.read_bytes()
            ext = path.suffix.lstrip(".") or "mp3"
            content_type = "audio/wav" if ext == "wav" else "audio/mpeg"
            key = build_slide_audio_key(
                workspace_id=workspace_id,
                video_presentation_id=video_presentation_id,
                slide_number=slide_number,
                ext=ext,
            )
            await backend.put(key, data, content_type=content_type)
        except Exception:
            logger.exception(
                "Failed to offload slide %s audio for video %s",
                slide_number,
                video_presentation_id,
            )
            continue
        slide["storage_backend"] = backend.backend_name
        slide["audio_storage_key"] = key
        slide.pop("audio_file", None)
        try:
            os.remove(local_path)
        except OSError:
            logger.warning("Could not delete local audio %s", local_path)
    return slides


def open_stream(storage_key: str) -> AsyncIterator[bytes]:
    return get_storage_backend().open_stream(storage_key)


async def purge(slides: list[dict[str, Any]] | None) -> None:
    if not slides:
        return
    backend = get_storage_backend()
    for slide in slides:
        key = slide.get("audio_storage_key")
        if key:
            await backend.delete(key)
        local_path = slide.get("audio_file")
        if local_path and os.path.isfile(local_path):
            try:
                os.remove(local_path)
            except OSError:
                logger.warning("Could not delete local audio %s", local_path)
