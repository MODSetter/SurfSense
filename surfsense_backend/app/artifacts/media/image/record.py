"""Record a generated image as an Artifact."""

from __future__ import annotations

import base64
import logging
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.artifacts.media.naming import primary_filename
from app.artifacts.persistence import ArtifactFileRole, ArtifactFormat
from app.artifacts.schemas import ArtifactFileInput, ArtifactSaved
from app.artifacts.service import save_artifact

logger = logging.getLogger(__name__)

PROVIDER_FETCH_TIMEOUT_SECONDS = 30


def _image_type(data: bytes) -> tuple[str, str]:
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


async def record(
    session: AsyncSession,
    *,
    workspace_id: int,
    prompt: str,
    response: dict[str, Any],
    provenance: dict[str, Any] | None = None,
    thread_id: int | None = None,
    tool_call_id: str | None = None,
    committed_by_turn: bool = False,
) -> ArtifactSaved:
    """Persist the first image of a provider response as an Artifact."""
    images = response.get("data")
    if not isinstance(images, list) or not images or not isinstance(images[0], dict):
        raise ValueError("image response carried no data entries")

    entry = images[0]
    data = await _bytes_from(entry)
    if not data:
        raise ValueError("image response resolved to empty bytes")

    extension, mime_type = _image_type(data)
    title = (prompt or "Generated image").strip()[:120]
    revised_prompt = entry.get("revised_prompt")
    metadata = {
        key: value
        for key, value in {
            **(provenance or {}),
            "prompt": prompt,
            "revised_prompt": revised_prompt if revised_prompt != prompt else None,
        }.items()
        if value is not None
    }

    return await save_artifact(
        session,
        workspace_id=workspace_id,
        thread_id=thread_id,
        tool_call_id=tool_call_id,
        title=title,
        markdown_representation=f"# {title}\n\nPrompt: {prompt}\n",
        committed_by_turn=committed_by_turn,
        files=[
            ArtifactFileInput(
                data=data,
                filename=primary_filename(title, extension=extension, fallback="image"),
                mime_type=mime_type,
                role=ArtifactFileRole.PRIMARY,
            )
        ],
        extra_metadata=metadata,
        format=ArtifactFormat.IMAGE,
    )
