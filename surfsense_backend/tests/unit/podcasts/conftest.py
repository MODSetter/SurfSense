"""Shared builders for podcast unit tests.

These tests exercise pure logic through public interfaces with no test doubles:
the brief and transcript factories build valid aggregates so each test states
only the fields it cares about. Stateful, persistence-backed paths (the lifecycle
service, the Celery task bodies) are covered by the integration suite against a
real database.
"""

from __future__ import annotations

import pytest

from app.podcasts.schemas import (
    DurationTarget,
    PodcastSpec,
    PodcastStyle,
    SpeakerRole,
    SpeakerSpec,
    Transcript,
    TranscriptTurn,
)


@pytest.fixture
def make_spec():
    """Factory for a valid :class:`PodcastSpec`; override only what matters."""

    def _make(
        *,
        language: str = "en",
        style: PodcastStyle = PodcastStyle.CONVERSATIONAL,
        speakers: list[SpeakerSpec] | None = None,
        min_seconds: int = 600,
        max_seconds: int = 1200,
        focus: str | None = None,
    ) -> PodcastSpec:
        if speakers is None:
            speakers = [
                SpeakerSpec(
                    slot=0,
                    name="Host",
                    role=SpeakerRole.HOST,
                    voice_id="kokoro:am_adam",
                ),
                SpeakerSpec(
                    slot=1,
                    name="Guest",
                    role=SpeakerRole.GUEST,
                    voice_id="kokoro:af_bella",
                ),
            ]
        return PodcastSpec(
            language=language,
            style=style,
            speakers=speakers,
            duration=DurationTarget(min_seconds=min_seconds, max_seconds=max_seconds),
            focus=focus,
        )

    return _make


@pytest.fixture
def make_transcript():
    """Factory for a valid :class:`Transcript`."""

    def _make(turns: list[tuple[int, str]] | None = None) -> Transcript:
        if turns is None:
            turns = [(0, "Welcome to the show."), (1, "Glad to be here.")]
        return Transcript(
            turns=[TranscriptTurn(speaker=slot, text=text) for slot, text in turns]
        )

    return _make
