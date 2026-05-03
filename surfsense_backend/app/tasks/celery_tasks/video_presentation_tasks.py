"""Celery tasks for video presentation generation."""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from sqlalchemy import select

from app.agents.video_presentation.graph import graph as video_presentation_graph
from app.agents.video_presentation.state import State as VideoPresentationState
from app.celery_app import celery_app
from app.config import config as app_config
from app.db import VideoPresentation, VideoPresentationStatus
from app.services.billable_calls import (
    BillingSettlementError,
    QuotaInsufficientError,
    _resolve_agent_billing_for_search_space,
    billable_call,
)
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

logger = logging.getLogger(__name__)

if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except AttributeError:
        logger.warning(
            "WindowsProactorEventLoopPolicy is unavailable; async subprocess support may fail."
        )


@asynccontextmanager
async def _celery_billable_session():
    """Session factory used by billable_call inside the Celery worker loop."""
    async with get_celery_session_maker()() as session:
        yield session


@celery_app.task(name="generate_video_presentation", bind=True)
def generate_video_presentation_task(
    self,
    video_presentation_id: int,
    source_content: str,
    search_space_id: int,
    user_prompt: str | None = None,
) -> dict:
    """
    Celery task to generate video presentation from source content.
    Updates existing video presentation record created by the tool.
    """
    try:
        return run_async_celery_task(
            lambda: _generate_video_presentation(
                video_presentation_id,
                source_content,
                search_space_id,
                user_prompt,
            )
        )
    except Exception as e:
        logger.error(f"Error generating video presentation: {e!s}")
        # Mark FAILED in a fresh loop — the previous loop is closed.
        # Swallow secondary failures; the row will simply stay in
        # GENERATING and be flushed by the periodic stale cleanup.
        try:
            run_async_celery_task(
                lambda: _mark_video_presentation_failed(video_presentation_id)
            )
        except Exception:
            logger.exception(
                "Failed to mark video presentation %s as failed",
                video_presentation_id,
            )
        return {"status": "failed", "video_presentation_id": video_presentation_id}


async def _mark_video_presentation_failed(video_presentation_id: int) -> None:
    """Mark a video presentation as failed in the database."""
    async with get_celery_session_maker()() as session:
        try:
            result = await session.execute(
                select(VideoPresentation).filter(
                    VideoPresentation.id == video_presentation_id
                )
            )
            video_pres = result.scalars().first()
            if video_pres:
                video_pres.status = VideoPresentationStatus.FAILED
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to mark video presentation as failed: {e}")


async def _generate_video_presentation(
    video_presentation_id: int,
    source_content: str,
    search_space_id: int,
    user_prompt: str | None = None,
) -> dict:
    """Generate video presentation and update existing record."""
    async with get_celery_session_maker()() as session:
        result = await session.execute(
            select(VideoPresentation).filter(
                VideoPresentation.id == video_presentation_id
            )
        )
        video_pres = result.scalars().first()

        if not video_pres:
            raise ValueError(f"VideoPresentation {video_presentation_id} not found")

        try:
            video_pres.status = VideoPresentationStatus.GENERATING
            await session.commit()

            try:
                (
                    owner_user_id,
                    billing_tier,
                    base_model,
                ) = await _resolve_agent_billing_for_search_space(
                    session,
                    search_space_id,
                    thread_id=video_pres.thread_id,
                )
            except ValueError as resolve_err:
                logger.error(
                    "VideoPresentation %s: cannot resolve billing for "
                    "search_space=%s: %s",
                    video_pres.id,
                    search_space_id,
                    resolve_err,
                )
                video_pres.status = VideoPresentationStatus.FAILED
                await session.commit()
                return {
                    "status": "failed",
                    "video_presentation_id": video_pres.id,
                    "reason": "billing_resolution_failed",
                }

            graph_config = {
                "configurable": {
                    "video_title": video_pres.title,
                    "search_space_id": search_space_id,
                    "user_prompt": user_prompt,
                }
            }

            initial_state = VideoPresentationState(
                source_content=source_content,
                db_session=session,
            )

            try:
                async with billable_call(
                    user_id=owner_user_id,
                    search_space_id=search_space_id,
                    billing_tier=billing_tier,
                    base_model=base_model,
                    quota_reserve_micros_override=app_config.QUOTA_DEFAULT_VIDEO_PRESENTATION_RESERVE_MICROS,
                    usage_type="video_presentation_generation",
                    call_details={
                        "video_presentation_id": video_pres.id,
                        "title": video_pres.title,
                        "thread_id": video_pres.thread_id,
                    },
                    billable_session_factory=_celery_billable_session,
                ):
                    graph_result = await video_presentation_graph.ainvoke(
                        initial_state, config=graph_config
                    )
            except QuotaInsufficientError as exc:
                logger.info(
                    "VideoPresentation %s denied: out of premium credits "
                    "(used=%d/%d remaining=%d)",
                    video_pres.id,
                    exc.used_micros,
                    exc.limit_micros,
                    exc.remaining_micros,
                )
                video_pres.status = VideoPresentationStatus.FAILED
                await session.commit()
                return {
                    "status": "failed",
                    "video_presentation_id": video_pres.id,
                    "reason": "premium_quota_exhausted",
                }
            except BillingSettlementError:
                logger.exception(
                    "VideoPresentation %s: premium billing settlement failed",
                    video_pres.id,
                )
                video_pres.status = VideoPresentationStatus.FAILED
                await session.commit()
                return {
                    "status": "failed",
                    "video_presentation_id": video_pres.id,
                    "reason": "billing_settlement_failed",
                }

            # Serialize slides (parsed content + audio info merged)
            slides_raw = graph_result.get("slides", [])
            audio_results_raw = graph_result.get("slide_audio_results", [])
            scene_codes_raw = graph_result.get("slide_scene_codes", [])

            audio_map = {}
            for ar in audio_results_raw:
                data = ar.model_dump() if hasattr(ar, "model_dump") else ar
                audio_map[data.get("slide_number", 0)] = data

            serializable_slides = []
            for slide in slides_raw:
                slide_data = (
                    slide.model_dump() if hasattr(slide, "model_dump") else dict(slide)
                )
                audio_data = audio_map.get(slide_data.get("slide_number", 0), {})
                slide_data["audio_file"] = audio_data.get("audio_file")
                slide_data["duration_seconds"] = audio_data.get("duration_seconds")
                slide_data["duration_in_frames"] = audio_data.get("duration_in_frames")
                serializable_slides.append(slide_data)

            serializable_scene_codes = []
            for sc in scene_codes_raw:
                sc_data = sc.model_dump() if hasattr(sc, "model_dump") else dict(sc)
                serializable_scene_codes.append(sc_data)

            video_pres.slides = serializable_slides
            video_pres.scene_codes = serializable_scene_codes
            video_pres.status = VideoPresentationStatus.READY
            logger.info(
                "VideoPresentation %s: committing READY slides=%d scene_codes=%d",
                video_pres.id,
                len(serializable_slides),
                len(serializable_scene_codes),
            )
            await session.commit()
            logger.info("VideoPresentation %s: READY commit complete", video_pres.id)

            logger.info(f"Successfully generated video presentation: {video_pres.id}")

            return {
                "status": "ready",
                "video_presentation_id": video_pres.id,
                "title": video_pres.title,
                "slide_count": len(serializable_slides),
            }

        except Exception as e:
            logger.error(f"Error in _generate_video_presentation: {e!s}")
            video_pres.status = VideoPresentationStatus.FAILED
            await session.commit()
            raise
