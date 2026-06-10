"""The podcast lifecycle: the guarantees the rest of the system relies on.

These tests drive the aggregate through :class:`PodcastService`'s public
methods and observe the resulting status and stored brief/transcript — the
domain's contract. They say nothing about how the service stores or flushes,
so they survive any refactor that preserves the lifecycle.
"""

from __future__ import annotations

import pytest

from app.podcasts.persistence import PodcastStatus
from app.podcasts.service import (
    InvalidTransition,
    PodcastService,
    PreconditionFailed,
    SpecConflict,
    read_spec,
    read_transcript,
)

pytestmark = pytest.mark.unit


async def test_a_podcast_progresses_from_creation_to_ready(
    fake_session, make_spec, make_transcript
):
    """The full happy path: create → brief → draft → review → render → ready."""
    service = PodcastService(fake_session)

    podcast = await service.create(title="Episode 1", search_space_id=7)
    assert podcast.status == PodcastStatus.PENDING

    spec = make_spec()
    await service.attach_brief(podcast, spec)
    assert podcast.status == PodcastStatus.AWAITING_BRIEF
    assert read_spec(podcast) == spec

    await service.begin_drafting(podcast)
    assert podcast.status == PodcastStatus.DRAFTING

    transcript = make_transcript()
    await service.attach_transcript(podcast, transcript)
    assert podcast.status == PodcastStatus.AWAITING_REVIEW
    assert read_transcript(podcast) == transcript

    await service.approve(podcast)
    assert podcast.status == PodcastStatus.RENDERING

    await service.attach_audio(
        podcast, storage_backend="local", storage_key="k", duration_seconds=42
    )
    assert podcast.status == PodcastStatus.READY
    assert podcast.duration_seconds == 42


async def test_drafting_requires_an_approved_brief(fake_session):
    """A brief must exist before drafting can begin."""
    service = PodcastService(fake_session)
    podcast = await service.create(title="No brief", search_space_id=1)

    with pytest.raises(PreconditionFailed):
        await service.begin_drafting(podcast)


async def test_rendering_requires_a_transcript(fake_session, make_spec):
    """Approval to render is refused when no transcript has been drafted."""
    service = PodcastService(fake_session)
    podcast = await service.create(title="No transcript", search_space_id=1)
    await service.attach_brief(podcast, make_spec())
    await service.begin_drafting(podcast)

    with pytest.raises(PreconditionFailed):
        await service.approve(podcast)


async def test_regenerate_returns_a_reviewed_transcript_to_drafting(
    fake_session, make_spec, make_transcript
):
    """At the go/no-go gate, rejecting sends the podcast back to drafting."""
    service = PodcastService(fake_session)
    podcast = await service.create(title="Redo", search_space_id=1)
    await service.attach_brief(podcast, make_spec())
    await service.begin_drafting(podcast)
    await service.attach_transcript(podcast, make_transcript())

    await service.regenerate(podcast)

    assert podcast.status == PodcastStatus.DRAFTING


async def test_brief_can_be_edited_at_the_gate_and_bumps_its_version(
    fake_session, make_spec
):
    """Editing the brief while awaiting review records it and advances version."""
    service = PodcastService(fake_session)
    podcast = await service.create(title="Editable", search_space_id=1)
    await service.attach_brief(podcast, make_spec(language="en"))
    starting_version = podcast.spec_version

    await service.update_spec(podcast, make_spec(language="fr"), starting_version)

    assert read_spec(podcast).language == "fr"
    assert podcast.spec_version == starting_version + 1


async def test_editing_a_brief_with_a_stale_version_conflicts(
    fake_session, make_spec
):
    """A concurrent edit racing on a stale version is rejected, not silently lost."""
    service = PodcastService(fake_session)
    podcast = await service.create(title="Raced", search_space_id=1)
    await service.attach_brief(podcast, make_spec())
    current = podcast.spec_version

    with pytest.raises(SpecConflict):
        await service.update_spec(podcast, make_spec(language="es"), current - 1)


async def test_brief_cannot_be_edited_after_the_gate_closes(
    fake_session, make_spec
):
    """Once drafting starts, the brief is settled and edits are refused."""
    service = PodcastService(fake_session)
    podcast = await service.create(title="Locked", search_space_id=1)
    await service.attach_brief(podcast, make_spec())
    await service.begin_drafting(podcast)

    with pytest.raises(InvalidTransition):
        await service.update_spec(podcast, make_spec(language="es"), podcast.spec_version)


async def test_a_podcast_can_be_cancelled_while_in_flight(fake_session, make_spec):
    """Cancellation is available from a non-terminal state."""
    service = PodcastService(fake_session)
    podcast = await service.create(title="Abort", search_space_id=1)
    await service.attach_brief(podcast, make_spec())

    await service.cancel(podcast)

    assert podcast.status == PodcastStatus.CANCELLED


async def test_failure_records_a_reason(fake_session):
    """Failing a podcast captures a human-readable reason."""
    service = PodcastService(fake_session)
    podcast = await service.create(title="Boom", search_space_id=1)

    await service.fail(podcast, "tts provider unavailable")

    assert podcast.status == PodcastStatus.FAILED
    assert podcast.error == "tts provider unavailable"


async def test_terminal_podcasts_reject_further_transitions(fake_session):
    """A finished podcast cannot be cancelled or otherwise moved."""
    service = PodcastService(fake_session)
    podcast = await service.create(title="Done", search_space_id=1)
    await service.cancel(podcast)

    with pytest.raises(InvalidTransition):
        await service.fail(podcast, "too late")
