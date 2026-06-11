"""HTTP surface for the podcast lifecycle.

Status is observed by the frontend through Zero, so these routes are about
actions (create, edit/approve the brief, regenerate, cancel) and audio delivery.
Each mutating route performs the guarded transition via the service, commits,
then enqueues the matching Celery task; lifecycle errors map to 409/422.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config as app_config
from app.db import (
    Permission,
    SearchSpace,
    SearchSpaceMembership,
    User,
    get_async_session,
)
from app.podcasts.generation.brief import propose_brief
from app.podcasts.persistence import Podcast, PodcastRepository
from app.podcasts.service import (
    InvalidTransition,
    PodcastService,
    PreconditionFailed,
    SpecConflict,
)
from app.podcasts.storage import open_audio_stream, purge_audio
from app.podcasts.tasks import draft_transcript_task
from app.podcasts.tts import get_text_to_speech
from app.podcasts.voices import (
    get_voice_catalog,
    provider_from_service,
    render_voice_preview,
)
from app.users import current_active_user
from app.utils.rbac import check_permission

from .schemas import (
    CreatePodcastRequest,
    PodcastDetail,
    PodcastSummary,
    UpdateSpecRequest,
    VoiceOption,
)

router = APIRouter()


@router.get("/podcasts", response_model=list[PodcastSummary])
async def list_podcasts(
    search_space_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    if skip < 0 or limit < 1:
        raise HTTPException(status_code=400, detail="Invalid pagination parameters")

    if search_space_id is not None:
        await _require(session, user, search_space_id, Permission.PODCASTS_READ)
        query = (
            select(Podcast)
            .where(Podcast.search_space_id == search_space_id)
            .order_by(Podcast.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
    else:
        query = (
            select(Podcast)
            .join(SearchSpace)
            .join(SearchSpaceMembership)
            .where(SearchSpaceMembership.user_id == user.id)
            .order_by(Podcast.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
    result = await session.execute(query)
    return list(result.scalars().all())


@router.get("/podcasts/voices", response_model=list[VoiceOption])
async def list_voices(language: str | None = None):
    """Voices the active TTS provider offers, optionally filtered by language."""
    if not app_config.TTS_SERVICE:
        raise HTTPException(status_code=503, detail="No TTS provider configured")

    provider = provider_from_service(app_config.TTS_SERVICE)
    catalog = get_voice_catalog()
    voices = (
        catalog.for_language(provider, language)
        if language
        else catalog.for_provider(provider)
    )
    return [
        VoiceOption(
            voice_id=v.voice_id,
            display_name=v.display_name,
            language=v.language,
            gender=v.gender.value,
        )
        for v in voices
    ]


@router.get("/podcasts/voices/{voice_id}/preview")
async def preview_voice(
    voice_id: str,
    user: User = Depends(current_active_user),
):
    """A short audio sample of a voice, so users pick by sound."""
    if not app_config.TTS_SERVICE:
        raise HTTPException(status_code=503, detail="No TTS provider configured")

    provider = provider_from_service(app_config.TTS_SERVICE)
    try:
        voice = get_voice_catalog().get(voice_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown voice") from None
    if voice.provider is not provider:
        raise HTTPException(
            status_code=404, detail="Voice not offered by the active TTS provider"
        )

    data, content_type = await render_voice_preview(voice, get_text_to_speech())
    return Response(content=data, media_type=content_type)


@router.post("/podcasts", response_model=PodcastDetail, status_code=201)
async def create_podcast(
    body: CreatePodcastRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    await _require(session, user, body.search_space_id, Permission.PODCASTS_CREATE)

    service = PodcastService(session)
    podcast = await service.create(
        title=body.title,
        search_space_id=body.search_space_id,
        thread_id=body.thread_id,
    )
    podcast.source_content = body.source_content

    spec = await propose_brief(
        session,
        search_space_id=body.search_space_id,
        speaker_count=body.speaker_count,
        min_minutes=body.min_minutes,
        max_minutes=body.max_minutes,
        focus=body.focus,
    )
    await service.attach_brief(podcast, spec)
    await session.commit()
    return PodcastDetail.of(podcast)


@router.get("/podcasts/{podcast_id}", response_model=PodcastDetail)
async def get_podcast(
    podcast_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    podcast = await _load(session, user, podcast_id, Permission.PODCASTS_READ)
    return PodcastDetail.of(podcast)


@router.patch("/podcasts/{podcast_id}/spec", response_model=PodcastDetail)
async def update_spec(
    podcast_id: int,
    body: UpdateSpecRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    podcast = await _load(session, user, podcast_id, Permission.PODCASTS_UPDATE)
    async with _lifecycle_errors():
        await PodcastService(session).update_spec(
            podcast, body.spec, body.expected_version
        )
    await session.commit()
    return PodcastDetail.of(podcast)


@router.post("/podcasts/{podcast_id}/brief/approve", response_model=PodcastDetail)
async def approve_brief(
    podcast_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Approve the brief and start drafting the transcript."""
    podcast = await _load(session, user, podcast_id, Permission.PODCASTS_UPDATE)
    async with _lifecycle_errors():
        await PodcastService(session).begin_drafting(podcast)
    await session.commit()
    draft_transcript_task.delay(podcast.id, podcast.search_space_id)
    return PodcastDetail.of(podcast)


@router.post(
    "/podcasts/{podcast_id}/transcript/regenerate", response_model=PodcastDetail
)
async def regenerate_transcript(
    podcast_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Reopen the brief gate for a fresh take; drafting waits for re-approval."""
    podcast = await _load(session, user, podcast_id, Permission.PODCASTS_UPDATE)
    async with _lifecycle_errors():
        await PodcastService(session).regenerate(podcast)
    await session.commit()
    return PodcastDetail.of(podcast)


@router.post("/podcasts/{podcast_id}/regenerate/revert", response_model=PodcastDetail)
async def revert_regeneration(
    podcast_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Back out of a regeneration and return to the finished episode."""
    podcast = await _load(session, user, podcast_id, Permission.PODCASTS_UPDATE)
    async with _lifecycle_errors():
        await PodcastService(session).revert_regeneration(podcast)
    await session.commit()
    return PodcastDetail.of(podcast)


@router.post("/podcasts/{podcast_id}/cancel", response_model=PodcastDetail)
async def cancel_podcast(
    podcast_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    podcast = await _load(session, user, podcast_id, Permission.PODCASTS_UPDATE)
    async with _lifecycle_errors():
        await PodcastService(session).cancel(podcast)
    await session.commit()
    return PodcastDetail.of(podcast)


@router.delete("/podcasts/{podcast_id}", response_model=dict)
async def delete_podcast(
    podcast_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    podcast = await _load(session, user, podcast_id, Permission.PODCASTS_DELETE)
    await purge_audio(podcast)
    await session.delete(podcast)
    await session.commit()
    return {"message": "Podcast deleted successfully"}


@router.get("/podcasts/{podcast_id}/stream")
async def stream_podcast(
    podcast_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    podcast = await _load(session, user, podcast_id, Permission.PODCASTS_READ)

    if podcast.storage_key:
        return StreamingResponse(
            open_audio_stream(podcast),
            media_type="audio/mpeg",
            headers={"Accept-Ranges": "bytes"},
        )

    # Back-compat: rows rendered before the storage migration kept a local path.
    if podcast.file_location and os.path.isfile(podcast.file_location):
        path = podcast.file_location

        def iterfile():
            with open(path, mode="rb") as handle:
                yield from handle

        return StreamingResponse(
            iterfile(),
            media_type="audio/mpeg",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Disposition": f"inline; filename={Path(path).name}",
            },
        )

    raise HTTPException(status_code=404, detail="Podcast audio not found")


async def _require(
    session: AsyncSession,
    user: User,
    search_space_id: int,
    permission: Permission,
) -> None:
    await check_permission(
        session,
        user,
        search_space_id,
        permission.value,
        "You don't have permission for podcasts in this search space",
    )


async def _load(
    session: AsyncSession,
    user: User,
    podcast_id: int,
    permission: Permission,
) -> Podcast:
    podcast = await PodcastRepository(session).get(podcast_id)
    if podcast is None:
        raise HTTPException(status_code=404, detail="Podcast not found")
    await _require(session, user, podcast.search_space_id, permission)
    return podcast


class _lifecycle_errors:
    """Map service lifecycle errors onto HTTP responses."""

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        if exc is None:
            return False
        if isinstance(exc, SpecConflict):
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if isinstance(exc, InvalidTransition):
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if isinstance(exc, PreconditionFailed):
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return False
