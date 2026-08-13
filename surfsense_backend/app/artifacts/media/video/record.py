"""Record a finished video presentation as an Artifact (cutover)."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.artifacts.media.legacy import existing_legacy_artifact, legacy_metadata
from app.artifacts.media.naming import primary_filename
from app.artifacts.media.video.storage import offload_slide_audio, open_stream
from app.artifacts.persistence import ArtifactFileRole, ArtifactFormat
from app.artifacts.schemas import ArtifactFileInput, ArtifactInput, ArtifactSaved
from app.artifacts.service import persist_artifact

logger = logging.getLogger(__name__)


def _to_artifact_input(
    *,
    workspace_id: int,
    title: str,
    markdown_representation: str,
    narration_audio: bytes,
    thread_id: int | None,
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
                data=narration_audio,
                filename=primary_filename(
                    title, extension="mp3", fallback="narration"
                ),
                mime_type="audio/mpeg",
                role=ArtifactFileRole.PRIMARY,
            ),
        ),
        thread_id=thread_id,
        format=ArtifactFormat.VIDEO,
        artifact_id=artifact_id,
        expected_generation=expected_generation,
        metadata=metadata,
    )


async def record(
    session: AsyncSession,
    video_pres: Any,
    slides: list[dict[str, Any]],
    scene_codes: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], ArtifactSaved | None]:
    """Offload slide audio, persist Artifact; return updated slides.

    Artifact write is best-effort; offload skips failed slides.
    """
    slides = await offload_slide_audio(
        slides,
        workspace_id=video_pres.workspace_id,
        video_presentation_id=video_pres.id,
    )
    saved: ArtifactSaved | None = None
    try:
        audio_key = next(
            (s.get("audio_storage_key") for s in slides if s.get("audio_storage_key")),
            None,
        )
        if not audio_key:
            return slides, None
        chunks = [chunk async for chunk in open_stream(audio_key)]
        audio = b"".join(chunks)
        if not audio:
            return slides, None

        outline = "\n".join(
            f"- Slide {s.get('slide_number')}: "
            f"{s.get('title') or s.get('heading') or 'Untitled'}"
            for s in slides
        )
        title = video_pres.title or "Video presentation"
        existing = await existing_legacy_artifact(
            session,
            workspace_id=video_pres.workspace_id,
            kind="video",
            legacy_id=video_pres.id,
        )
        # Durable Remotion payload on Artifact — strip local audio_file paths;
        # audio_storage_key + artifact slide-audio route are the read path.
        remotion_slides = []
        for slide in slides:
            copy = {
                key: value
                for key, value in slide.items()
                if key not in {"audio_file", "storage_backend"}
            }
            remotion_slides.append(copy)
        payload = _to_artifact_input(
            workspace_id=video_pres.workspace_id,
            title=title,
            markdown_representation=f"# {title}\n\n{outline}\n",
            narration_audio=audio,
            thread_id=video_pres.thread_id,
            metadata=legacy_metadata(
                "video",
                video_pres.id,
                {
                    "slide_count": len(slides),
                    "scene_code_count": len(scene_codes),
                    "slides": remotion_slides,
                    "scene_codes": scene_codes,
                },
            ),
            artifact_id=existing.id if existing else None,
            expected_generation=existing.generation if existing else None,
        )
        saved = await persist_artifact(session, payload)
    except Exception:
        logger.exception(
            "artifacts.media.video.record failed for %s",
            getattr(video_pres, "id", None),
        )
    return slides, saved
