"""Record a finished image generation as an Artifact."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.artifacts.media.image.storage import offload_b64, open_stream
from app.artifacts.media.legacy import existing_legacy_artifact, legacy_metadata
from app.artifacts.media.naming import primary_filename
from app.artifacts.persistence import ArtifactFileRole, ArtifactFormat
from app.artifacts.schemas import ArtifactFileInput, ArtifactInput, ArtifactSaved
from app.artifacts.service import persist_artifact

logger = logging.getLogger(__name__)


def _to_artifact_input(
    *,
    workspace_id: int,
    title: str,
    markdown_representation: str,
    image: bytes,
    metadata: dict[str, Any],
    artifact_id: int | None,
    expected_generation: int | None,
) -> ArtifactInput:
    return ArtifactInput(
        workspace_id=workspace_id,
        title=title,
        markdown_representation=markdown_representation,
        files=(
            ArtifactFileInput(
                data=image,
                filename=primary_filename(title, extension="png", fallback="image"),
                mime_type="image/png",
                role=ArtifactFileRole.PRIMARY,
            ),
        ),
        format=ArtifactFormat.IMAGE,
        artifact_id=artifact_id,
        expected_generation=expected_generation,
        metadata=metadata,
    )


async def record(session: AsyncSession, image_gen: Any) -> ArtifactSaved | None:
    """Offload b64 on ``image_gen.response_data`` and persist an Artifact.

    ``image_gen`` is an ImageGeneration ORM row. Best-effort: failures log only.
    """
    try:
        response_data = image_gen.response_data
        if not isinstance(response_data, dict):
            return None

        image_gen.response_data = await offload_b64(
            response_data,
            workspace_id=image_gen.workspace_id,
            image_gen_id=image_gen.id,
        )

        images = (image_gen.response_data or {}).get("data") or []
        if not images or not isinstance(images[0], dict):
            return None
        key = images[0].get("storage_key")
        if not key:
            return None

        chunks = [chunk async for chunk in open_stream(key)]
        data = b"".join(chunks)
        if not data:
            return None

        prompt = image_gen.prompt or "Generated image"
        existing = await existing_legacy_artifact(
            session,
            workspace_id=image_gen.workspace_id,
            kind="image",
            legacy_id=image_gen.id,
        )
        payload = _to_artifact_input(
            workspace_id=image_gen.workspace_id,
            title=prompt[:120],
            markdown_representation=f"# Generated image\n\nPrompt: {prompt}\n",
            image=data,
            metadata=legacy_metadata(
                "image",
                image_gen.id,
                {"prompt": prompt, "model": getattr(image_gen, "model", None)},
            ),
            artifact_id=existing.id if existing else None,
            expected_generation=existing.generation if existing else None,
        )
        return await persist_artifact(session, payload)
    except Exception:
        logger.exception(
            "artifacts.media.image.record failed for %s",
            getattr(image_gen, "id", None),
        )
        return None
