"""Celery tasks for podcast generation."""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from sqlalchemy import select

from app.agents.podcaster.graph import graph as podcaster_graph
from app.agents.podcaster.state import State as PodcasterState
from app.celery_app import celery_app
from app.config import config as app_config
from app.db import Podcast, PodcastStatus
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


# =============================================================================
# Content-based podcast generation (for new-chat)
# =============================================================================


@asynccontextmanager
async def _celery_billable_session():
    """Session factory used by billable_call inside the Celery worker loop."""
    async with get_celery_session_maker()() as session:
        yield session


@celery_app.task(name="generate_content_podcast", bind=True)
def generate_content_podcast_task(
    self,
    podcast_id: int,
    source_content: str,
    search_space_id: int,
    user_prompt: str | None = None,
) -> dict:
    """
    Celery task to generate podcast from source content.
    Updates existing podcast record created by the tool.
    """
    try:
        return run_async_celery_task(
            lambda: _generate_content_podcast(
                podcast_id,
                source_content,
                search_space_id,
                user_prompt,
            )
        )
    except Exception as e:
        logger.error(f"Error generating content podcast: {e!s}")
        try:
            run_async_celery_task(lambda: _mark_podcast_failed(podcast_id))
        except Exception:
            logger.exception("Failed to mark podcast %s as failed", podcast_id)
        return {"status": "failed", "podcast_id": podcast_id}


async def _mark_podcast_failed(podcast_id: int) -> None:
    """Mark a podcast as failed in the database."""
    async with get_celery_session_maker()() as session:
        try:
            result = await session.execute(
                select(Podcast).filter(Podcast.id == podcast_id)
            )
            podcast = result.scalars().first()
            if podcast:
                podcast.status = PodcastStatus.FAILED
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to mark podcast as failed: {e}")


async def _generate_content_podcast(
    podcast_id: int,
    source_content: str,
    search_space_id: int,
    user_prompt: str | None = None,
) -> dict:
    """Generate content-based podcast and update existing record."""
    async with get_celery_session_maker()() as session:
        result = await session.execute(select(Podcast).filter(Podcast.id == podcast_id))
        podcast = result.scalars().first()

        if not podcast:
            raise ValueError(f"Podcast {podcast_id} not found")

        try:
            podcast.status = PodcastStatus.GENERATING
            await session.commit()

            try:
                (
                    owner_user_id,
                    billing_tier,
                    base_model,
                ) = await _resolve_agent_billing_for_search_space(
                    session,
                    search_space_id,
                    thread_id=podcast.thread_id,
                )
            except ValueError as resolve_err:
                logger.error(
                    "Podcast %s: cannot resolve billing for search_space=%s: %s",
                    podcast.id,
                    search_space_id,
                    resolve_err,
                )
                podcast.status = PodcastStatus.FAILED
                await session.commit()
                return {
                    "status": "failed",
                    "podcast_id": podcast.id,
                    "reason": "billing_resolution_failed",
                }

            graph_config = {
                "configurable": {
                    "podcast_title": podcast.title,
                    "search_space_id": search_space_id,
                    "user_prompt": user_prompt,
                }
            }

            initial_state = PodcasterState(
                source_content=source_content,
                db_session=session,
            )

            try:
                async with billable_call(
                    user_id=owner_user_id,
                    search_space_id=search_space_id,
                    billing_tier=billing_tier,
                    base_model=base_model,
                    quota_reserve_micros_override=app_config.QUOTA_DEFAULT_PODCAST_RESERVE_MICROS,
                    usage_type="podcast_generation",
                    call_details={
                        "podcast_id": podcast.id,
                        "title": podcast.title,
                        "thread_id": podcast.thread_id,
                    },
                    billable_session_factory=_celery_billable_session,
                ):
                    graph_result = await podcaster_graph.ainvoke(
                        initial_state, config=graph_config
                    )
            except QuotaInsufficientError as exc:
                logger.info(
                    "Podcast %s denied: out of premium credits "
                    "(used=%d/%d remaining=%d)",
                    podcast.id,
                    exc.used_micros,
                    exc.limit_micros,
                    exc.remaining_micros,
                )
                podcast.status = PodcastStatus.FAILED
                await session.commit()
                return {
                    "status": "failed",
                    "podcast_id": podcast.id,
                    "reason": "premium_quota_exhausted",
                }
            except BillingSettlementError:
                logger.exception(
                    "Podcast %s: premium billing settlement failed",
                    podcast.id,
                )
                podcast.status = PodcastStatus.FAILED
                await session.commit()
                return {
                    "status": "failed",
                    "podcast_id": podcast.id,
                    "reason": "billing_settlement_failed",
                }

            podcast_transcript = graph_result.get("podcast_transcript", [])
            file_path = graph_result.get("final_podcast_file_path", "")

            serializable_transcript = []
            for entry in podcast_transcript:
                if hasattr(entry, "speaker_id"):
                    serializable_transcript.append(
                        {"speaker_id": entry.speaker_id, "dialog": entry.dialog}
                    )
                else:
                    serializable_transcript.append(
                        {
                            "speaker_id": entry.get("speaker_id", 0),
                            "dialog": entry.get("dialog", ""),
                        }
                    )

            podcast.podcast_transcript = serializable_transcript
            podcast.file_location = file_path
            podcast.status = PodcastStatus.READY
            logger.info(
                "Podcast %s: committing READY transcript_entries=%d file=%s",
                podcast.id,
                len(serializable_transcript),
                file_path,
            )
            await session.commit()
            logger.info("Podcast %s: READY commit complete", podcast.id)

            logger.info(f"Successfully generated podcast: {podcast.id}")

            return {
                "status": "ready",
                "podcast_id": podcast.id,
                "title": podcast.title,
                "transcript_entries": len(serializable_transcript),
            }

        except Exception as e:
            logger.error(f"Error in _generate_content_podcast: {e!s}")
            podcast.status = PodcastStatus.FAILED
            await session.commit()
            raise
