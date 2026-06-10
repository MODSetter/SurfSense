"""Transcript-drafting task: DRAFTING -> AWAITING_REVIEW.

The expensive, LLM-heavy step, so it runs under ``billable_call`` exactly like
the legacy generator. The API has already moved the row to DRAFTING and stored
the approved brief; this task drafts the long-form transcript and opens the
go/no-go gate.
"""

from __future__ import annotations

import logging

from app.celery_app import celery_app
from app.config import config as app_config
from app.podcasts.generation.transcript.graph import graph as transcript_graph
from app.podcasts.generation.transcript.state import TranscriptState
from app.podcasts.persistence import PodcastRepository
from app.podcasts.service import PodcastService, read_spec
from app.services.billable_calls import (
    BillingSettlementError,
    QuotaInsufficientError,
    _resolve_agent_billing_for_search_space,
    billable_call,
)
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

from .runtime import billable_session, mark_failed

logger = logging.getLogger(__name__)


@celery_app.task(name="podcast.draft_transcript", bind=True)
def draft_transcript_task(self, podcast_id: int, search_space_id: int) -> dict:
    try:
        return run_async_celery_task(
            lambda: _draft_transcript(podcast_id, search_space_id)
        )
    except Exception as exc:  # noqa: BLE001 - record and report, never crash worker
        logger.error("Podcast %s drafting failed: %s", podcast_id, exc)
        run_async_celery_task(lambda: mark_failed(podcast_id, str(exc)))
        return {"status": "failed", "podcast_id": podcast_id}


async def _draft_transcript(podcast_id: int, search_space_id: int) -> dict:
    async with get_celery_session_maker()() as session:
        repo = PodcastRepository(session)
        service = PodcastService(session)
        podcast = await repo.get(podcast_id)
        if podcast is None:
            raise ValueError(f"podcast {podcast_id} not found")

        spec = read_spec(podcast)
        if spec is None:
            raise ValueError(f"podcast {podcast_id} has no approved brief")

        owner_id, tier, base_model = await _resolve_agent_billing_for_search_space(
            session, search_space_id, thread_id=podcast.thread_id
        )

        state = TranscriptState(
            db_session=session, source_content=podcast.source_content or ""
        )
        config = {
            "configurable": {
                "search_space_id": search_space_id,
                "spec": spec,
                "focus": spec.focus,
            }
        }

        try:
            async with billable_call(
                user_id=owner_id,
                search_space_id=search_space_id,
                billing_tier=tier,
                base_model=base_model,
                quota_reserve_micros_override=app_config.QUOTA_DEFAULT_PODCAST_RESERVE_MICROS,
                usage_type="podcast_generation",
                call_details={"podcast_id": podcast_id, "title": podcast.title},
                billable_session_factory=billable_session,
            ):
                result = await transcript_graph.ainvoke(state, config=config)
        except QuotaInsufficientError:
            await service.fail(podcast, "premium quota exhausted")
            await session.commit()
            return {"status": "failed", "podcast_id": podcast_id, "reason": "quota"}
        except BillingSettlementError:
            await service.fail(podcast, "billing settlement failed")
            await session.commit()
            return {"status": "failed", "podcast_id": podcast_id, "reason": "billing"}

        await service.attach_transcript(podcast, result["transcript"])
        await session.commit()
        return {"status": "awaiting_review", "podcast_id": podcast_id}
