"""The podcast pipeline: a reviewed brief becomes an outline, then segments."""

import pytest

from modules.artifacts.podcast.brief import Duration, PodcastBrief, Speaker, Style
from modules.llm.profile import Tier
from modules.llm.providers.protocols import SpokenTurn, SynthesizedAudio, Voice
from modules.llm.resolution import ModelResolutionError, ResolvedGeneration
from worker.studio.media.audio.podcast import draft, outline, pipeline
from worker.studio.shared import generate

pytestmark = pytest.mark.unit

MODEL = ResolvedGeneration(
    type("Selection", (), {"name": "qwen3:8b", "tier": Tier.CAPABLE})(), None
)

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
    prompt = outline.prompt(Tier.CAPABLE, BRIEF, "the risks")

    assert "1200 words" in prompt
    assert "5 segments" in prompt
    assert "pt-BR" in prompt and "interview" in prompt
    assert "1. Sam (host)" in prompt and "2. Lee (expert)" in prompt
    assert "the risks" in prompt


def test_segments_are_kept_in_order_and_sized_when_the_model_forgets() -> None:
    """Titles are required; missing target words get an even share of the total."""
    raw = (
        '{"title": "Saturn", "segments": [{"title": "Opening", "talking_points": '
        '["hello"]}, {"talking_points": ["no title"]}, '
        '{"title": "Close", "target_words": 200}]}'
    )
    planned = outline.parse(raw, BRIEF)

    assert planned.title == "Saturn"
    assert [segment.title for segment in planned.segments] == ["Opening", "Close"]
    assert planned.segments[0].talking_points == ["hello"]
    assert planned.segments[0].target_words == 600
    assert planned.segments[1].target_words == 200
    assert outline.parse('{"segments": [{"title": "x"}]}', BRIEF).title == "Podcast"


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
    opening = draft.prompt(Tier.CAPABLE, BRIEF, SEGMENTS[0], 1, 2, None)
    assert "segment 1 of 2" in opening
    assert "opening segment" in opening
    assert "- say hi" in opening and "about 100 words" in opening

    middle = draft.prompt(Tier.CAPABLE, BRIEF, SEGMENTS[1], 2, 2, "Sam: Welcome.")
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
    repairs: list[generate.Repair | None] = []

    def fake_run_model(
        model: object,
        system: str,
        sources: list,
        *,
        repair: generate.Repair | None = None,
    ) -> str:
        prompts.append(system)
        repairs.append(repair)
        return next(replies)

    monkeypatch.setattr("worker.studio.shared.generate.run_model", fake_run_model)

    with pytest.raises(ValueError, match="Segment 2 of 2 could not be drafted"):
        draft.draft(MODEL, BRIEF, SEGMENTS, [])

    assert len(prompts) == 4
    # The nudge rides a repair turn carrying the bad reply, not the prompt, so
    # "your previous reply" refers to something the model was actually shown.
    assert repairs[0] is None
    assert repairs[1] is not None
    assert repairs[1].reply == "not json"
    assert "not valid JSON" in repairs[1].instruction
    assert "not valid JSON" not in prompts[1]
    assert "Sam: Hi." in prompts[2]


class FakeVoice:
    """A TextToSpeech that records what it was asked to say."""

    def __init__(self) -> None:
        self.turns: list[SpokenTurn] = []

    def voices(self) -> list[Voice]:
        return [Voice("pm_alex", "Alex", "pt-BR"), Voice("pf_dora", "Dora", "pt-BR")]

    async def synthesize(self, turns: list[SpokenTurn]) -> SynthesizedAudio:
        self.turns = turns
        return SynthesizedAudio(b"RIFFfake", "audio/wav")


def _episode(monkeypatch: pytest.MonkeyPatch, *replies: str) -> tuple[FakeVoice, list]:
    voice = FakeVoice()
    monkeypatch.setattr(
        "worker.studio.media.audio.podcast.pipeline.resolve_text_to_speech",
        lambda: voice,
    )
    queue = iter(replies)
    prompts: list[str] = []

    def fake_run_model(model: object, system: str, sources: list) -> str:
        prompts.append(system)
        return next(queue)

    monkeypatch.setattr("worker.studio.shared.generate.run_model", fake_run_model)
    return voice, prompts


def test_an_episode_is_planned_then_drafted_per_segment_then_voiced_per_speaker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One outline call, one call per segment; each line is voiced by its speaker's
    chosen voice; the transcript names the speakers and is the searchable body."""
    voice, prompts = _episode(
        monkeypatch,
        '{"title": "Saturn Rings", "segments": [{"title": "Open"}, {"title": "Close"}]}',
        '{"turns": [{"speaker": 1, "text": "Welcome."}]}',
        '{"turns": [{"speaker": 2, "text": "Goodbye."}]}',
    )

    built = pipeline.render(MODEL, [], "the risks", BRIEF.model_dump(mode="json"))

    assert len(prompts) == 3 and "the risks" in prompts[0]
    assert [(t.voice, t.text) for t in voice.turns] == [
        ("pm_alex", "Welcome."),
        ("pf_dora", "Goodbye."),
    ]
    assert built.title == "Saturn Rings"
    assert built.primary == b"RIFFfake"
    assert built.primary_filename == "saturn-rings.wav"
    assert "**Sam:** Welcome." in built.markdown
    assert "**Lee:** Goodbye." in built.markdown


def test_an_episode_too_short_to_voice_fails_before_synthesis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A single line is not an episode; no CPU minutes go into voicing it."""
    voice, _ = _episode(
        monkeypatch,
        '{"title": "T", "segments": [{"title": "Only"}]}',
        '{"turns": [{"speaker": 1, "text": "Hi."}]}',
    )

    with pytest.raises(ValueError, match="too short"):
        pipeline.render(MODEL, [], None, BRIEF.model_dump(mode="json"))
    assert voice.turns == []


def test_without_a_voice_engine_the_text_model_is_never_called(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing voice engine fails before any model tokens are spent."""
    monkeypatch.setattr(
        "modules.llm.providers.kokoro.provider.missing_files",
        lambda: ["kokoro-v1.0.onnx"],
    )
    monkeypatch.setattr(
        "worker.studio.shared.generate.run_model",
        lambda *a: pytest.fail("the text model was called"),
    )

    with pytest.raises(ModelResolutionError, match="Kokoro"):
        pipeline.render(None, [], None, BRIEF.model_dump(mode="json"))
