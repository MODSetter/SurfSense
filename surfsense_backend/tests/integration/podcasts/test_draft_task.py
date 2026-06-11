"""The transcript-drafting task against a real database.

Drafting is the expensive LLM step, so it runs under ``billable_call``. The
behavior that protects users' money: when billing succeeds, a drafted transcript
opens the review gate (DRAFTING -> AWAITING_REVIEW); when billing denies or
settlement fails, the podcast ends FAILED with no transcript left behind. The DB,
service, and transcript persistence run for real; only the true externals are
faked — billing (the metering boundary) and the generation graph (the LLM).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.podcasts.persistence import PodcastStatus
from app.podcasts.service import read_transcript
from app.podcasts.tasks import draft
from app.services.billable_calls import (
    BillingSettlementError,
    QuotaInsufficientError,
)

from .conftest import build_transcript

pytestmark = pytest.mark.integration


def _wire_billing(monkeypatch, *, billable_call, transcript=None) -> None:
    """Replace the billing + LLM externals the draft body reaches for."""

    async def _resolver(_session, _search_space_id, *, thread_id=None):
        return uuid4(), "free", "openrouter/model"

    async def _ainvoke(_state, config=None):
        return {"transcript": transcript}

    monkeypatch.setattr(draft, "_resolve_agent_billing_for_search_space", _resolver)
    monkeypatch.setattr(draft, "billable_call", billable_call)
    monkeypatch.setattr(draft, "transcript_graph", SimpleNamespace(ainvoke=_ainvoke))


async def test_successful_billing_opens_review_gate_with_transcript(
    monkeypatch, db_search_space, make_podcast, bind_task_session
):
    podcast = await make_podcast(
        search_space_id=db_search_space.id, status=PodcastStatus.DRAFTING
    )

    @asynccontextmanager
    async def _ok(**_kwargs):
        yield SimpleNamespace()

    _wire_billing(monkeypatch, billable_call=_ok, transcript=build_transcript())

    result = await draft._draft_transcript(podcast.id, db_search_space.id)

    assert result["status"] == "awaiting_review"
    assert podcast.status == PodcastStatus.AWAITING_REVIEW
    assert read_transcript(podcast) is not None


async def test_quota_denial_fails_the_podcast_without_a_transcript(
    monkeypatch, db_search_space, make_podcast, bind_task_session
):
    podcast = await make_podcast(
        search_space_id=db_search_space.id, status=PodcastStatus.DRAFTING
    )

    @asynccontextmanager
    async def _deny(**_kwargs):
        raise QuotaInsufficientError(
            usage_type="podcast_generation",
            used_micros=5_000_000,
            limit_micros=5_000_000,
            remaining_micros=0,
        )
        yield  # pragma: no cover - unreachable, satisfies the CM protocol

    _wire_billing(monkeypatch, billable_call=_deny)

    result = await draft._draft_transcript(podcast.id, db_search_space.id)

    assert result["reason"] == "quota"
    assert podcast.status == PodcastStatus.FAILED
    assert read_transcript(podcast) is None


async def test_billing_settlement_failure_fails_the_podcast(
    monkeypatch, db_search_space, make_podcast, bind_task_session
):
    podcast = await make_podcast(
        search_space_id=db_search_space.id, status=PodcastStatus.DRAFTING
    )

    @asynccontextmanager
    async def _settlement_fails(**_kwargs):
        yield SimpleNamespace()
        raise BillingSettlementError(
            usage_type="podcast_generation",
            user_id=uuid4(),
            cause=RuntimeError("finalize failed"),
        )

    _wire_billing(
        monkeypatch, billable_call=_settlement_fails, transcript=build_transcript()
    )

    result = await draft._draft_transcript(podcast.id, db_search_space.id)

    assert result["reason"] == "billing"
    assert podcast.status == PodcastStatus.FAILED
