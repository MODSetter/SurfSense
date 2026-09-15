"""The podcast pipeline: a reviewed brief becomes an outline, then segments."""

import pytest

from modules.artifacts.podcast.brief import Duration, PodcastBrief, Speaker, Style
from worker.studio.media.audio.podcast import outline

pytestmark = pytest.mark.unit

BRIEF = PodcastBrief(
    language="pt-BR",
    style=Style.INTERVIEW,
    duration=Duration.STANDARD,
    speakers=[
        Speaker(name="Sam", role="host", voice="pm_alex"),
        Speaker(name="Lee", role="expert", voice="pf_dora"),
    ],
)


def test_the_outline_prompt_is_sized_to_the_preset_and_names_the_cast() -> None:
    """Standard is 8 minutes: about 1200 words in about 5 segments."""
    prompt = outline.prompt(BRIEF, "the risks")

    assert "1200 words" in prompt
    assert "5 segments" in prompt
    assert "pt-BR" in prompt and "interview" in prompt
    assert "1. Sam (host)" in prompt and "2. Lee (expert)" in prompt
    assert "the risks" in prompt


def test_segments_are_kept_in_order_and_sized_when_the_model_forgets() -> None:
    """Titles are required; missing target words get an even share of the total."""
    raw = (
        '{"segments": [{"title": "Opening", "talking_points": ["hello"]}, '
        '{"talking_points": ["no title"]}, {"title": "Close", "target_words": 200}]}'
    )
    segments = outline.parse(raw, BRIEF)

    assert [segment.title for segment in segments] == ["Opening", "Close"]
    assert segments[0].talking_points == ["hello"]
    assert segments[0].target_words == 600
    assert segments[1].target_words == 200


def test_an_outline_without_segments_is_an_error() -> None:
    """Nothing to draft is a failure the user reads, not an empty episode."""
    with pytest.raises(ValueError, match="outline"):
        outline.parse('{"segments": []}', BRIEF)
