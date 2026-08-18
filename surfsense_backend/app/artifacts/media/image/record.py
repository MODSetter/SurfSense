"""Record a generated image as an Artifact."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.artifacts.media.image.bytes import image_bytes_from_response
from app.artifacts.media.naming import primary_filename
from app.artifacts.persistence import ArtifactFileRole, ArtifactFormat
from app.artifacts.schemas import ArtifactFileInput, ArtifactSaved
from app.artifacts.service import save_artifact

logger = logging.getLogger(__name__)


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
    data, mime_type, extension = await image_bytes_from_response(response)
    entry = response["data"][0]
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
