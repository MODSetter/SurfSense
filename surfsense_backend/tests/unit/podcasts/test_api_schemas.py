"""The API read model the frontend renders from.

``PodcastDetail.of`` is the contract the detail view and action responses
depend on: it exposes the deserialized brief and transcript and a simple
``has_audio`` flag the client can't derive from the published Zero columns.
These tests drive real podcasts through the service, then assert the read model
reflects their state.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.podcasts.api.schemas import PodcastDetail
from app.podcasts.persistence import PodcastStatus
from app.podcasts.service import PodcastService

pytestmark = pytest.mark.unit


def _stamp(podcast):
    """Give a transient row the id and created_at a persisted one would have.

    A detail response is only ever built from a saved podcast; without a real
    database, we stand in the primary key and timestamp the DB would assign.
    """
    podcast.id = 1
    podcast.created_at = datetime.now(UTC)
    return podcast


async def test_a_fresh_podcast_exposes_no_brief_transcript_or_audio(fake_session):
    service = PodcastService(fake_session)
    podcast = _stamp(await service.create(title="New", search_space_id=3))

    detail = PodcastDetail.of(podcast)

    assert detail.status == PodcastStatus.PENDING
    assert detail.spec is None
    assert detail.transcript is None
    assert detail.has_audio is False


async def test_an_awaiting_brief_podcast_exposes_the_deserialized_brief(
    fake_session, make_spec
):
    service = PodcastService(fake_session)
    podcast = _stamp(await service.create(title="Brief", search_space_id=3))
    await service.attach_brief(podcast, make_spec(language="fr"))

    detail = PodcastDetail.of(podcast)

    assert detail.spec is not None
    assert detail.spec.language == "fr"


async def test_a_ready_podcast_reports_available_audio(
    fake_session, make_spec, make_transcript
):
    service = PodcastService(fake_session)
    podcast = _stamp(await service.create(title="Done", search_space_id=3))
    await service.attach_brief(podcast, make_spec())
    await service.begin_drafting(podcast)
    await service.attach_transcript(podcast, make_transcript())
    await service.approve(podcast)
    await service.attach_audio(
        podcast, storage_backend="local", storage_key="k", duration_seconds=120
    )

    detail = PodcastDetail.of(podcast)

    assert detail.status == PodcastStatus.READY
    assert detail.has_audio is True
    assert detail.duration_seconds == 120
    assert detail.transcript is not None
    assert detail.error is None
