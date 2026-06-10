"""Failure recording shared by the podcast tasks.

When a task body raises, ``mark_failed`` is the safety net that records the
reason on the row. Its contract has two halves worth securing: a still-running
podcast is moved to FAILED with the reason, and a podcast that already reached a
terminal state is left exactly as it was rather than forced. Only the database
(a real boundary) is doubled; the lifecycle service runs for real.
"""

from __future__ import annotations

import pytest

from app.podcasts.persistence import Podcast, PodcastStatus
from app.podcasts.tasks import runtime

pytestmark = pytest.mark.unit


def _podcast(status: PodcastStatus) -> Podcast:
    podcast = Podcast(title="Episode", search_space_id=1, status=status, spec_version=1)
    podcast.id = 1
    return podcast


async def test_marking_failed_records_the_reason_on_a_running_podcast(
    monkeypatch, session_maker_for, make_celery_session
):
    podcast = _podcast(PodcastStatus.DRAFTING)
    session = make_celery_session(podcast)
    monkeypatch.setattr(runtime, "get_celery_session_maker", session_maker_for(session))

    await runtime.mark_failed(1, "tts provider unavailable")

    assert podcast.status == PodcastStatus.FAILED
    assert podcast.error == "tts provider unavailable"


async def test_marking_failed_leaves_an_already_terminal_podcast_untouched(
    monkeypatch, session_maker_for, make_celery_session
):
    podcast = _podcast(PodcastStatus.CANCELLED)
    session = make_celery_session(podcast)
    monkeypatch.setattr(runtime, "get_celery_session_maker", session_maker_for(session))

    await runtime.mark_failed(1, "too late")

    assert podcast.status == PodcastStatus.CANCELLED


async def test_marking_a_missing_podcast_failed_is_a_no_op(
    monkeypatch, session_maker_for, make_celery_session
):
    session = make_celery_session(None)
    monkeypatch.setattr(runtime, "get_celery_session_maker", session_maker_for(session))

    await runtime.mark_failed(999, "gone")  # must not raise
