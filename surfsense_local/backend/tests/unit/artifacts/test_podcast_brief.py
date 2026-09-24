import pytest

from modules.artifacts.podcast import brief
from modules.llm.providers.protocols import Voice

VOICES = [
    Voice("af_heart", "Heart", ("en-US",)),
    Voice("am_adam", "Adam", ("en-US",)),
    Voice("pf_dora", "Dora", ("pt-BR",)),
]


def _speaker(name: str, voice: str, role: str = "host") -> dict:
    return {"name": name, "role": role, "voice": voice}


def test_no_options_means_the_proposed_brief() -> None:
    """A job without a brief gets the defaults: two English hosts, standard length."""
    result = brief.validated(VOICES, None)
    assert result.language == "en-US"
    assert result.style is brief.Style.CONVERSATIONAL
    assert result.duration is brief.Duration.STANDARD
    assert [(s.role, s.voice) for s in result.speakers] == [
        (brief.Role.HOST, "af_heart"),
        (brief.Role.GUEST, "am_adam"),
    ]


def test_a_voice_from_another_language_is_refused_by_speaker_name() -> None:
    """The message names the speaker so the form can point at the right row."""
    raw = {"language": "en-US", "speakers": [_speaker("Ana", "pf_dora")]}
    with pytest.raises(ValueError, match=r"Ana.*en-US"):
        brief.validated(VOICES, raw)


def test_two_speakers_cannot_share_a_voice() -> None:
    """Same voice twice makes the hosts indistinguishable, so it is refused."""
    raw = {
        "language": "en-US",
        "speakers": [_speaker("A", "af_heart"), _speaker("B", "af_heart", "guest")],
    }
    with pytest.raises(ValueError, match="voice"):
        brief.validated(VOICES, raw)


def test_speaker_count_is_bounded() -> None:
    """One to six speakers; the roster prompt and the voice catalog size the cap."""
    raw = {"language": "en-US", "speakers": []}
    with pytest.raises(ValueError, match="speakers"):
        brief.validated(VOICES, raw)


def test_a_valid_brief_round_trips_as_a_plain_dict() -> None:
    """What the job stores is the normalised brief, ready for the worker to reload."""
    raw = {
        "language": "en-US",
        "style": "interview",
        "duration": "long",
        "speakers": [
            _speaker("  Sam ", "am_adam"),
            _speaker("Lee", "af_heart", "expert"),
        ],
    }
    stored = brief.validated(VOICES, raw).model_dump(mode="json")
    assert stored["speakers"][0]["name"] == "Sam"
    assert brief.PodcastBrief.model_validate(stored).duration is brief.Duration.LONG
