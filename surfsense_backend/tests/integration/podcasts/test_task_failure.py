"""The task failure safety net (``mark_failed``) against a real database.

When a task body raises, ``mark_failed`` records the reason on the row. Its
contract has two halves worth securing: a still-running podcast moves to FAILED
with the reason, while one that already reached a terminal state is left exactly
as it was rather than forced. A missing row is a no-op, never a crash.
"""

from __future__ import annotations

import pytest

from app.podcasts.persistence import PodcastStatus
from app.podcasts.tasks import runtime

pytestmark = pytest.mark.integration


async def test_marking_failed_records_the_reason_on_a_running_podcast(
    db_search_space, make_podcast, bind_task_session
):
    podcast = await make_podcast(
        search_space_id=db_search_space.id, status=PodcastStatus.DRAFTING
    )

    await runtime.mark_failed(podcast.id, "tts provider unavailable")

    assert podcast.status == PodcastStatus.FAILED
    assert podcast.error == "tts provider unavailable"


async def test_marking_failed_leaves_an_already_terminal_podcast_untouched(
    db_search_space, make_podcast, bind_task_session
):
    podcast = await make_podcast(
        search_space_id=db_search_space.id, status=PodcastStatus.READY
    )

    await runtime.mark_failed(podcast.id, "too late")

    assert podcast.status == PodcastStatus.READY


async def test_marking_a_missing_podcast_failed_is_a_no_op(bind_task_session):
    await runtime.mark_failed(987654321, "gone")  # must not raise
