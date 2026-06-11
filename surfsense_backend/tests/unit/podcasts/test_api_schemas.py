"""The API read model the frontend renders from.

``PodcastDetail.of`` maps a stored podcast row to the detail view and action
responses: it exposes the deserialized brief and transcript and a simple
``has_audio`` flag the client can't derive from the published Zero columns. Each
test builds a row in one lifecycle shape and asserts the mapping reflects it.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.podcasts.api.schemas import PodcastDetail
from app.podcasts.persistence import Podcast, PodcastStatus

pytestmark = pytest.mark.unit


def _podcast(*, status: PodcastStatus = PodcastStatus.PENDING, **columns) -> Podcast:
    """A persisted-looking row: the id and created_at a saved podcast would carry."""
    podcast = Podcast(
        title="Episode",
        search_space_id=3,
        status=status,
        spec_version=1,
        **columns,
    )
    podcast.id = 1
    podcast.created_at = datetime.now(UTC)
    return podcast


def test_a_fresh_podcast_exposes_no_brief_transcript_or_audio():
    detail = PodcastDetail.of(_podcast())

    assert detail.status == PodcastStatus.PENDING
    assert detail.spec is None
    assert detail.transcript is None
    assert detail.has_audio is False


def test_an_awaiting_brief_podcast_exposes_the_deserialized_brief(make_spec):
    podcast = _podcast(
        status=PodcastStatus.AWAITING_BRIEF,
        spec=make_spec(language="fr").model_dump(mode="json"),
    )

    detail = PodcastDetail.of(podcast)

    assert detail.spec is not None
    assert detail.spec.language == "fr"


def test_a_legacy_episode_still_exposes_its_transcript_and_audio():
    # Pre-rework rows stored [{speaker_id, dialog}] and a local file path;
    # they must keep flowing through the new read model, not fail validation.
    podcast = _podcast(
        status=PodcastStatus.READY,
        podcast_transcript=[
            {"speaker_id": 0, "dialog": "Welcome back."},
            {"speaker_id": 1, "dialog": "Glad to be here."},
        ],
        file_location="/var/old/podcast.mp3",
    )

    detail = PodcastDetail.of(podcast)

    assert detail.has_audio is True
    assert detail.transcript is not None
    assert [(turn.speaker, turn.text) for turn in detail.transcript.turns] == [
        (0, "Welcome back."),
        (1, "Glad to be here."),
    ]


def test_a_ready_podcast_reports_available_audio(make_spec, make_transcript):
    podcast = _podcast(
        status=PodcastStatus.READY,
        spec=make_spec().model_dump(mode="json"),
        podcast_transcript=make_transcript().model_dump(mode="json"),
        storage_backend="local",
        storage_key="k",
        duration_seconds=120,
    )

    detail = PodcastDetail.of(podcast)

    assert detail.status == PodcastStatus.READY
    assert detail.has_audio is True
    assert detail.duration_seconds == 120
    assert detail.transcript is not None
    assert detail.error is None
