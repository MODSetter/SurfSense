"""
Routes for public chat access via immutable snapshots.

All public endpoints use share_token for access - no authentication required
for read operations. Clone requires authentication.
"""

import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import get_async_session
from app.observability import analytics as ph_analytics
from app.schemas.new_chat import (
    CloneResponse,
    PublicChatResponse,
)
from app.services.public_chat_service import (
    clone_from_snapshot,
    get_public_chat,
    get_snapshot_artifact_file,
    get_snapshot_podcast,
    get_snapshot_video_artifact,
    get_snapshot_video_presentation,
)
from app.users import require_session_context

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/{share_token}", response_model=PublicChatResponse)
async def read_public_chat(
    share_token: str,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get a public chat snapshot by share token.

    No authentication required.
    Returns immutable snapshot data (sanitized, citations stripped).
    """
    return await get_public_chat(session, share_token)


@router.post("/{share_token}/clone", response_model=CloneResponse)
async def clone_public_chat(
    share_token: str,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
):
    user = auth.user
    """
    Clone a public chat snapshot to the user's account.

    Creates thread and copies messages.
    Requires authentication.
    """
    result = await clone_from_snapshot(session, share_token, user)

    # Share-link conversion — only observable server-side.
    ph_analytics.capture_for(
        auth,
        "public_chat_cloned",
        {
            "workspace_id": result.workspace_id,
            "chat_id": result.thread_id,
        },
        groups={"workspace": str(result.workspace_id)},
    )

    return result


@router.get("/{share_token}/artifacts/{artifact_id}/content")
async def stream_public_artifact_file(
    share_token: str,
    artifact_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    """Stream an artifact's primary file to a public viewer.

    No authentication required — the share token grants access, and only to
    artifacts the shared thread produced.
    """
    file = await get_snapshot_artifact_file(session, share_token, artifact_id)
    if not file:
        raise HTTPException(status_code=404, detail="Artifact not found")

    from app.file_storage.factory import get_storage_backend

    backend = get_storage_backend(file.storage_backend)
    # Verify first so a missing object is a 404, not a mid-stream crash.
    if not await backend.exists(file.storage_key):
        raise HTTPException(status_code=404, detail="Artifact is no longer available")

    return StreamingResponse(
        backend.open_stream(file.storage_key),
        media_type=file.mime_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


def _public_artifact_slides(
    share_token: str,
    artifact_id: int,
    slides: list[dict],
) -> list[dict]:
    """Slide payload with share-scoped audio URLs, storage keys stripped."""
    result = []
    for raw in slides:
        slide = dict(raw)
        slide_number = slide.get("slide_number")
        has_audio = bool(
            slide.pop("audio_storage_key", None) or slide.pop("audio_file", None)
        )
        slide.pop("storage_backend", None)
        if has_audio and isinstance(slide_number, int):
            slide["audio_url"] = (
                f"/api/v1/public/{share_token}/artifacts/{artifact_id}"
                f"/slides/{slide_number}/audio"
            )
        else:
            slide["audio_url"] = None
        result.append(slide)
    return result


@router.get("/{share_token}/artifacts/{artifact_id}/video")
async def get_public_artifact_video(
    share_token: str,
    artifact_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    """Remotion payload for a video Artifact in a public snapshot.

    No authentication required — the share token grants access, and only to
    video artifacts the shared thread produced.
    """
    artifact = await get_snapshot_video_artifact(session, share_token, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Video presentation not found")

    meta = artifact.artifact_metadata or {}
    slides = meta.get("slides")
    scene_codes = meta.get("scene_codes")
    if not isinstance(slides, list) or not isinstance(scene_codes, list):
        raise HTTPException(
            status_code=404, detail="Video Remotion payload not available"
        )

    return {
        "artifact_id": artifact.id,
        "title": artifact.document.title if artifact.document else None,
        "status": "ready",
        "slides": _public_artifact_slides(share_token, artifact.id, slides),
        "scene_codes": scene_codes,
        "slide_count": len(slides),
    }


@router.get("/{share_token}/artifacts/{artifact_id}/slides/{slide_number}/audio")
async def stream_public_artifact_slide_audio(
    share_token: str,
    artifact_id: int,
    slide_number: int,
    session: AsyncSession = Depends(get_async_session),
):
    """Stream a slide's audio from a video Artifact in a public snapshot."""
    from pathlib import Path

    artifact = await get_snapshot_video_artifact(session, share_token, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Video presentation not found")

    slides = (artifact.artifact_metadata or {}).get("slides") or []
    slide_data = next(
        (
            slide
            for slide in slides
            if isinstance(slide, dict) and slide.get("slide_number") == slide_number
        ),
        None,
    )
    if slide_data is None:
        raise HTTPException(status_code=404, detail=f"Slide {slide_number} not found")

    storage_key = slide_data.get("audio_storage_key")
    if not storage_key:
        raise HTTPException(status_code=404, detail="Slide audio file not found")

    from app.artifacts.media.video import open_stream

    ext = Path(str(storage_key)).suffix.lower()
    media_type = "audio/wav" if ext == ".wav" else "audio/mpeg"
    return StreamingResponse(
        open_stream(str(storage_key)),
        media_type=media_type,
        headers={"Accept-Ranges": "bytes"},
    )


@router.get("/{share_token}/podcasts/{podcast_id}")
async def get_public_podcast(
    share_token: str,
    podcast_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get podcast details from a public chat snapshot.

    No authentication required - the share_token provides access.
    Returns podcast info including transcript.
    """
    podcast_info = await get_snapshot_podcast(session, share_token, podcast_id)

    if not podcast_info:
        raise HTTPException(status_code=404, detail="Podcast not found")

    return {
        "id": podcast_info.get("original_id"),
        "title": podcast_info.get("title"),
        "status": "ready",
        "podcast_transcript": podcast_info.get("transcript"),
    }


@router.get("/{share_token}/podcasts/{podcast_id}/stream")
async def stream_public_podcast(
    share_token: str,
    podcast_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Stream a podcast from a public chat snapshot.

    No authentication required - the share_token provides access.
    Looks up podcast by original_id in the snapshot's podcasts array.
    """
    podcast_info = await get_snapshot_podcast(session, share_token, podcast_id)

    if not podcast_info:
        raise HTTPException(status_code=404, detail="Podcast not found")

    storage_key = podcast_info.get("storage_key")
    if storage_key:
        from app.file_storage.factory import get_storage_backend

        backend = get_storage_backend()
        # Verify first so a missing object is a 404, not a mid-stream crash.
        if not await backend.exists(storage_key):
            raise HTTPException(
                status_code=404, detail="Podcast audio is no longer available"
            )
        return StreamingResponse(
            backend.open_stream(storage_key),
            media_type="audio/mpeg",
            headers={"Accept-Ranges": "bytes"},
        )

    # Legacy fallback for snapshots taken before the storage migration.
    file_path = podcast_info.get("file_path")

    if not file_path or not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Podcast audio file not found")

    def iterfile():
        with open(file_path, mode="rb") as file_like:
            yield from file_like

    return StreamingResponse(
        iterfile(),
        media_type="audio/mpeg",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Disposition": f"inline; filename={os.path.basename(file_path)}",
        },
    )


@router.get("/{share_token}/video-presentations/{video_presentation_id}")
async def get_public_video_presentation(
    share_token: str,
    video_presentation_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get video presentation details from a public chat snapshot.

    No authentication required - the share_token provides access.
    Returns slide data (with public audio URLs) and scene codes.
    """
    vp_info = await get_snapshot_video_presentation(
        session, share_token, video_presentation_id
    )

    if not vp_info:
        raise HTTPException(status_code=404, detail="Video presentation not found")

    slides = vp_info.get("slides") or []
    public_slides = _replace_audio_paths_with_public_urls(
        share_token, video_presentation_id, slides
    )

    return {
        "id": vp_info.get("original_id"),
        "title": vp_info.get("title"),
        "status": "ready",
        "slides": public_slides,
        "scene_codes": vp_info.get("scene_codes"),
        "slide_count": len(slides) if slides else None,
    }


@router.get(
    "/{share_token}/video-presentations/{video_presentation_id}/slides/{slide_number}/audio"
)
async def stream_public_slide_audio(
    share_token: str,
    video_presentation_id: int,
    slide_number: int,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Stream a slide's audio from a public chat snapshot.

    No authentication required - the share_token provides access.
    """
    from pathlib import Path

    vp_info = await get_snapshot_video_presentation(
        session, share_token, video_presentation_id
    )

    if not vp_info:
        raise HTTPException(status_code=404, detail="Video presentation not found")

    slides = vp_info.get("slides") or []
    slide_data = None
    for s in slides:
        if s.get("slide_number") == slide_number:
            slide_data = s
            break

    if not slide_data:
        raise HTTPException(status_code=404, detail=f"Slide {slide_number} not found")

    file_path = slide_data.get("audio_file")
    if not file_path or not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Slide audio file not found")

    ext = Path(file_path).suffix.lower()
    media_type = "audio/wav" if ext == ".wav" else "audio/mpeg"

    def iterfile():
        with open(file_path, mode="rb") as file_like:
            yield from file_like

    return StreamingResponse(
        iterfile(),
        media_type=media_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Disposition": f"inline; filename={Path(file_path).name}",
        },
    )


def _replace_audio_paths_with_public_urls(
    share_token: str,
    video_presentation_id: int,
    slides: list[dict],
) -> list[dict]:
    """Replace server-local audio_file paths with public streaming API URLs."""
    result = []
    for slide in slides:
        slide_copy = dict(slide)
        slide_number = slide_copy.get("slide_number")
        audio_file = slide_copy.pop("audio_file", None)

        if audio_file and slide_number is not None:
            slide_copy["audio_url"] = (
                f"/api/v1/public/{share_token}"
                f"/video-presentations/{video_presentation_id}"
                f"/slides/{slide_number}/audio"
            )
        else:
            slide_copy["audio_url"] = None

        result.append(slide_copy)
    return result
