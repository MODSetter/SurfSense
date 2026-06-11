"""The brief and transcript contracts.

A brief is what a user approves before any tokens or audio are spent, so its
validation rules are real behavior: they are the guardrails that keep a
nonsensical or ambiguous brief from ever reaching the expensive stages. These
tests pin those rules through construction of the public Pydantic models.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.podcasts.schemas import (
    DurationTarget,
    PodcastSpec,
    PodcastStyle,
    SpeakerRole,
    SpeakerSpec,
    Transcript,
    TranscriptTurn,
    normalize_language_tag,
)

pytestmark = pytest.mark.unit


def _speaker(slot: int, voice_id: str = "kokoro:am_adam") -> SpeakerSpec:
    return SpeakerSpec(
        slot=slot, name=f"Speaker {slot}", role=SpeakerRole.HOST, voice_id=voice_id
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("EN", "en"),
        ("en-US", "en-US"),
        ("PT-BR", "pt-BR"),
        ("  fr  ", "fr"),
    ],
)
def test_language_is_normalized_to_canonical_form(raw, expected):
    """The primary subtag is lowercased and surrounding space trimmed."""
    assert normalize_language_tag(raw) == expected


@pytest.mark.parametrize("invalid", ["", "e", "english!", "123", "en_US"])
def test_invalid_language_tags_are_rejected(invalid):
    """Tags that are not BCP-47-shaped never reach a brief."""
    with pytest.raises(ValueError):
        normalize_language_tag(invalid)


def test_spec_normalizes_its_language_on_construction():
    """A brief stores a canonical language regardless of how it was entered."""
    spec = PodcastSpec(
        language="EN-us",
        speakers=[_speaker(0)],
        duration=DurationTarget(min_minutes=5, max_minutes=10),
    )
    assert spec.language == "en-us"


def test_speakers_must_have_unique_slots():
    """Slots are the join key to transcript turns, so duplicates are invalid."""
    with pytest.raises(ValidationError):
        PodcastSpec(
            language="en",
            speakers=[_speaker(0), _speaker(0, voice_id="kokoro:af_bella")],
            duration=DurationTarget(min_minutes=5, max_minutes=10),
        )


def test_a_brief_needs_at_least_one_speaker():
    with pytest.raises(ValidationError):
        PodcastSpec(
            language="en",
            speakers=[],
            duration=DurationTarget(min_minutes=5, max_minutes=10),
        )


def test_a_monologue_brief_carries_exactly_one_speaker():
    spec = PodcastSpec(
        language="en",
        style=PodcastStyle.MONOLOGUE,
        speakers=[_speaker(0)],
        duration=DurationTarget(min_minutes=5, max_minutes=10),
    )
    assert spec.style is PodcastStyle.MONOLOGUE


def test_a_monologue_brief_rejects_multiple_speakers():
    """One voice is what 'monologue' means; a second speaker is a user error."""
    with pytest.raises(ValidationError):
        PodcastSpec(
            language="en",
            style=PodcastStyle.MONOLOGUE,
            speakers=[_speaker(0), _speaker(1, voice_id="kokoro:af_bella")],
            duration=DurationTarget(min_minutes=5, max_minutes=10),
        )


def test_duration_rejects_an_inverted_range():
    """A max below the min is a user error caught at the brief gate."""
    with pytest.raises(ValidationError):
        DurationTarget(min_minutes=20, max_minutes=10)


def test_duration_midpoint_is_where_drafting_aims():
    assert DurationTarget(min_minutes=10, max_minutes=20).midpoint_minutes == 15


def test_blank_focus_becomes_absent():
    """Whitespace-only steer is treated as no steer."""
    spec = PodcastSpec(
        language="en",
        speakers=[_speaker(0)],
        duration=DurationTarget(min_minutes=5, max_minutes=10),
        focus="   ",
    )
    assert spec.focus is None


def test_speaker_for_returns_the_speaker_bound_to_a_slot():
    spec = PodcastSpec(
        language="en",
        speakers=[_speaker(0), _speaker(1, voice_id="kokoro:af_bella")],
        duration=DurationTarget(min_minutes=5, max_minutes=10),
    )
    assert spec.speaker_for(1).voice_id == "kokoro:af_bella"


def test_speaker_for_raises_when_no_speaker_matches():
    spec = PodcastSpec(
        language="en",
        speakers=[_speaker(0)],
        duration=DurationTarget(min_minutes=5, max_minutes=10),
    )
    with pytest.raises(KeyError):
        spec.speaker_for(99)


def test_transcript_word_count_sums_spoken_words():
    """Word count is what drafting checks runtime against, so it must be exact."""
    transcript = Transcript(
        turns=[
            TranscriptTurn(speaker=0, text="hello there world"),
            TranscriptTurn(speaker=1, text="one two"),
        ]
    )
    assert transcript.word_count == 5


def test_blank_transcript_turns_are_rejected():
    with pytest.raises(ValidationError):
        TranscriptTurn(speaker=0, text="   ")


def test_a_transcript_needs_at_least_one_turn():
    with pytest.raises(ValidationError):
        Transcript(turns=[])
