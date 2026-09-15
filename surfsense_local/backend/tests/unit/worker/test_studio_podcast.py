"""The podcast pipeline: a reviewed brief becomes an outline, then segments."""

import pytest

from modules.artifacts.podcast.brief import Duration, PodcastBrief, Speaker, Style
from worker.studio.media.audio.podcast import draft, outline

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


SEGMENTS = [
    outline.Segment("Opening", ["say hi"], 100),
    outline.Segment("Rings", ["Galileo, 1610"], 300),
]


def test_the_segment_prompt_places_the_beat_and_continues_from_the_recap() -> None:
    """The model knows where it is in the episode and what was just said."""
    opening = draft.prompt(BRIEF, SEGMENTS[0], 1, 2, None)
    assert "segment 1 of 2" in opening
    assert "opening segment" in opening
    assert "- say hi" in opening and "about 100 words" in opening

    middle = draft.prompt(BRIEF, SEGMENTS[1], 2, 2, "Sam: Welcome.")
    assert "Sam: Welcome." in middle and "do not repeat" in middle
    assert "1. Sam (host)" in middle and "pt-BR" in middle


def test_turns_are_attributed_by_slot_or_name_and_strangers_are_dropped() -> None:
    """Small models answer with a number, a numeric string or the name; all map
    to a cast member. A line for nobody in the cast is left out."""
    raw = (
        '{"turns": [{"speaker": 1, "text": "Hi."}, {"speaker": "2", "text": "Hello."}, '
        '{"speaker": "lee", "text": "Again."}, {"speaker": 7, "text": "Who?"}, '
        '{"speaker": 1, "text": ""}]}'
    )
    turns = draft.parse(raw, BRIEF)
    assert [(turn.speaker, turn.text) for turn in turns] == [
        (1, "Hi."),
        (2, "Hello."),
        (2, "Again."),
    ]
    with pytest.raises(ValueError, match="dialogue"):
        draft.parse('{"turns": [{"speaker": 9, "text": "x"}]}', BRIEF)


def test_the_recap_is_the_tail_of_the_dialogue_by_name() -> None:
    """Continuity costs at most RECAP_CHARS of context per segment."""
    assert draft.recap([], BRIEF) is None
    turns = [draft.Turn(1, "a" * 700), draft.Turn(2, "b" * 700)]
    text = draft.recap(turns, BRIEF)
    assert text is not None
    assert len(text) == draft.RECAP_CHARS
    assert text.endswith("Lee: " + "b" * 700)


def test_a_broken_reply_is_retried_once_then_reported_by_segment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One bad JSON reply costs one more call; two in a row fail with the beat."""
    replies = iter(
        ["not json", '{"turns": [{"speaker": 1, "text": "Hi."}]}', "no", "no"]
    )
    prompts: list[str] = []

    def fake_run_model(model: object, system: str, sources: list) -> str:
        prompts.append(system)
        return next(replies)

    monkeypatch.setattr("worker.studio.shared.generate.run_model", fake_run_model)

    with pytest.raises(ValueError, match="Segment 2 of 2 could not be drafted"):
        draft.draft(object(), BRIEF, SEGMENTS, [])

    assert len(prompts) == 4
    assert "only the JSON" in prompts[1] and "only the JSON" not in prompts[0]
    assert "Sam: Hi." in prompts[2]
