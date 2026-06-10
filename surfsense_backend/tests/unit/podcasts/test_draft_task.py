"""The transcript-drafting task's billing gate.

Drafting is the expensive LLM step, so it runs under ``billable_call``. The
behavior that protects users' money: if billing denies the reservation the
podcast must end FAILED with no transcript, and only when billing succeeds does
a drafted transcript open the review gate. These tests fake the true
boundaries — the database, the billing system, and the generation graph — and
assert the podcast's resulting state, never how those boundaries were called.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.podcasts.persistence import Podcast, PodcastStatus
from app.podcasts.service import read_transcript
from app.podcasts.tasks import draft
from app.services.billable_calls import (
    BillingSettlementError,
    QuotaInsufficientError,
)

pytestmark = pytest.mark.unit


def _drafting_podcast(make_spec) -> Podcast:
    """A podcast already at DRAFTING with an approved brief, as the API leaves it."""
    podcast = Podcast(
        title="Episode",
        search_space_id=42,
        status=PodcastStatus.DRAFTING,
        spec_version=1,
    )
    podcast.id = 1
    podcast.thread_id = None
    podcast.spec = make_spec().model_dump(mode="json")
    podcast.source_content = "Some source material to discuss."
    return podcast


def _wire_boundaries(monkeypatch, *, session, billable_call, transcript=None):
    """Replace every external dependency the task body reaches for."""
    monkeypatch.setattr(draft, "get_celery_session_maker", lambda: (lambda: session))

    async def _resolver(_session, _search_space_id, *, thread_id=None):
        return uuid4(), "free", "openrouter/model"

    monkeypatch.setattr(
        draft, "_resolve_agent_billing_for_search_space", _resolver
    )
    monkeypatch.setattr(draft, "billable_call", billable_call)

    async def _ainvoke(_state, config=None):
        return {"transcript": transcript}

    monkeypatch.setattr(draft, "transcript_graph", SimpleNamespace(ainvoke=_ainvoke))


async def test_successful_billing_opens_the_review_gate_with_a_transcript(
    monkeypatch, make_celery_session, make_spec, make_transcript
):
    podcast = _drafting_podcast(make_spec)
    session = make_celery_session(podcast)

    @asynccontextmanager
    async def _ok(**_kwargs):
        yield SimpleNamespace()

    _wire_boundaries(
        monkeypatch, session=session, billable_call=_ok, transcript=make_transcript()
    )

    result = await draft._draft_transcript(podcast_id=1, search_space_id=42)

    assert podcast.status == PodcastStatus.AWAITING_REVIEW
    assert read_transcript(podcast) is not None
    assert result["status"] == "awaiting_review"


async def test_quota_denial_fails_the_podcast_without_a_transcript(
    monkeypatch, make_celery_session, make_spec
):
    """A denied reservation must not leave a half-drafted, billable mess."""
    podcast = _drafting_podcast(make_spec)
    session = make_celery_session(podcast)

    @asynccontextmanager
    async def _deny(**_kwargs):
        raise QuotaInsufficientError(
            usage_type="podcast_generation",
            used_micros=5_000_000,
            limit_micros=5_000_000,
            remaining_micros=0,
        )
        yield  # pragma: no cover - unreachable, satisfies the CM protocol

    _wire_boundaries(monkeypatch, session=session, billable_call=_deny)

    result = await draft._draft_transcript(podcast_id=1, search_space_id=42)

    assert podcast.status == PodcastStatus.FAILED
    assert read_transcript(podcast) is None
    assert result["reason"] == "quota"


async def test_billing_settlement_failure_fails_the_podcast(
    monkeypatch, make_celery_session, make_spec, make_transcript
):
    podcast = _drafting_podcast(make_spec)
    session = make_celery_session(podcast)

    @asynccontextmanager
    async def _settlement_fails(**_kwargs):
        yield SimpleNamespace()
        raise BillingSettlementError(
            usage_type="podcast_generation",
            user_id=uuid4(),
            cause=RuntimeError("finalize failed"),
        )

    _wire_boundaries(
        monkeypatch,
        session=session,
        billable_call=_settlement_fails,
        transcript=make_transcript(),
    )

    result = await draft._draft_transcript(podcast_id=1, search_space_id=42)

    assert podcast.status == PodcastStatus.FAILED
    assert result["reason"] == "billing"
