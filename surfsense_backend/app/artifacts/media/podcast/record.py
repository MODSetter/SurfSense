"""Record a finished podcast as an Artifact (cutover).

Audio blobs live in ``app.artifacts.media.podcast.storage``; this writes the Artifact.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.artifacts.media.legacy import existing_legacy_artifact, legacy_metadata
from app.artifacts.media.naming import primary_filename
from app.artifacts.persistence import ArtifactFileRole, ArtifactFormat
from app.artifacts.schemas import ArtifactFileInput, ArtifactInput, ArtifactSaved
from app.artifacts.service import persist_artifact

logger = logging.getLogger(__name__)


def _to_artifact_input(
    *,
    workspace_id: int,
    podcast_id: int,
    title: str,
    markdown_representation: str,
    audio: bytes,
    thread_id: int | None,
    artifact_id: int | None,
    expected_version: int | None,
) -> ArtifactInput:
    return ArtifactInput(
        workspace_id=workspace_id,
        title=title,
        markdown_representation=markdown_representation,
        files=(
            ArtifactFileInput(
                data=audio,
                filename=primary_filename(title, extension="mp3", fallback="podcast"),
                mime_type="audio/mpeg",
                role=ArtifactFileRole.PRIMARY,
            ),
        ),
        thread_id=thread_id,
        format=ArtifactFormat.PODCAST,
        artifact_id=artifact_id,
        expected_version=expected_version,
        metadata=legacy_metadata("podcast", podcast_id),
    )


def _representation_from_transcript(title: str, transcript: Any | None) -> str:
    turns = getattr(transcript, "turns", None) or []
    body = "\n\n".join(
        f"**Speaker {turn.speaker}:** {turn.text}" for turn in turns
    )
    return f"# {title}\n\n{body}"


async def record(
    session: AsyncSession,
    podcast: Any,
    *,
    audio: bytes,
    transcript: Any | None = None,
) -> ArtifactSaved | None:
    """Persist an Artifact for a READY podcast. Best-effort."""
    try:
        title = podcast.title or "Podcast"
        existing = await existing_legacy_artifact(
            session,
            workspace_id=podcast.workspace_id,
            kind="podcast",
            legacy_id=podcast.id,
        )
        payload = _to_artifact_input(
            workspace_id=podcast.workspace_id,
            podcast_id=podcast.id,
            title=title,
            markdown_representation=_representation_from_transcript(title, transcript),
            audio=audio,
            thread_id=podcast.thread_id,
            artifact_id=existing.id if existing else None,
            expected_version=existing.version if existing else None,
        )
        return await persist_artifact(session, payload)
    except Exception:
        logger.exception(
            "artifacts.media.podcast.record failed for %s",
            getattr(podcast, "id", None),
        )
        return None
