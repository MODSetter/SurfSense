"""Media kinds: visual (a drawn image, a built SVG) and audio (a voiced podcast)."""

import pytest

from modules.llm.providers.protocols import (
    GeneratedImage,
    SpokenTurn,
    SynthesizedAudio,
    Voice,
)
from modules.llm.resolution import ModelResolutionError, ResolvedImageGeneration
from worker.studio.media.audio.podcast import pipeline as podcast
from worker.studio.media.visual.image import pipeline as image
from worker.studio.media.visual.infographic import pipeline as infographic
from worker.studio.shared.artifact import Source

pytestmark = pytest.mark.unit

PNG = b"\x89PNG\r\n\x1a\nfake image bytes"


def test_image_stores_the_returned_png() -> None:
    """The selected ImageGenerator result becomes the artifact's primary file."""

    class FakeImageGenerator:
        async def generate(self, model: str, prompt: str) -> GeneratedImage:
            assert model == "flux"
            assert "Saturn" in prompt
            return GeneratedImage(PNG, "image/png")

    selection = type("Selection", (), {"name": "flux"})()
    model = ResolvedImageGeneration(selection, FakeImageGenerator())
    built = image.render(model, [Source(1, "Saturn", "rings")], "make it bold")

    assert built.primary == PNG
    assert built.primary_mime == "image/png"
    assert built.primary_filename == "image.png"
    assert built.title == "make it bold"


def test_infographic_paints_the_brief_the_chat_model_wrote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two steps: the chat model distils the facts, the image model draws them."""
    monkeypatch.setattr(
        "worker.studio.shared.generate.run_model",
        lambda *_: (
            '{"title":"Saturn","summary":"Rings","sections":'
            '[{"label":"Count","value":"7","detail":"Main rings"}]}'
        ),
    )
    painted: list[str] = []

    class FakeImageGenerator:
        async def generate(self, model: str, prompt: str) -> GeneratedImage:
            painted.append(prompt)
            return GeneratedImage(PNG, "image/png")

    selection = type("Selection", (), {"name": "flux"})()
    painter = ResolvedImageGeneration(selection, FakeImageGenerator())
    sources = [Source(1, "Saturn", "Galileo saw the rings in 1610.")]
    built = infographic.render(painter, None, sources, None)

    # The image prompt carries the brief and a style, not the raw sources.
    assert "Saturn" in painted[0] and "Count: 7" in painted[0]
    assert "1610" not in painted[0]
    assert "sketchnote" in painted[0]
    assert built.primary == PNG
    assert built.primary_mime == "image/png"
    assert built.primary_filename == "saturn.png"
    # The brief is the searchable body, so the picture is findable by its facts.
    assert built.title == "Saturn"
    assert "**7**" in built.markdown


class FakeVoice:
    """A TextToSpeech with two voices that records what it was asked to say."""

    def __init__(self) -> None:
        self.turns: list[SpokenTurn] = []

    def voices(self) -> list[Voice]:
        return [Voice("lead", "Lead"), Voice("guest", "Guest")]

    async def synthesize(self, turns: list[SpokenTurn]) -> SynthesizedAudio:
        self.turns = turns
        return SynthesizedAudio(b"RIFFfake", "audio/wav")


def test_podcast_voices_a_two_host_transcript() -> None:
    """The transcript is the searchable body; the engine's audio is the file."""
    raw = (
        '{"title": "Saturn", "turns": [{"speaker": "A", "text": "Hi."}, '
        '{"speaker": "B", "text": "Tell me more."}]}'
    )
    built = podcast.build(raw, FakeVoice())

    assert built.primary == b"RIFFfake"
    assert built.primary_mime == "audio/wav"
    assert built.primary_filename == "saturn.wav"
    assert "**A:** Hi." in built.markdown
    assert "**B:** Tell me more." in built.markdown


def test_podcast_gives_each_host_one_of_the_engines_voices() -> None:
    """Hosts take the engine's first and last voice; no voice id is hard-coded."""
    voice = FakeVoice()
    raw = (
        '{"title": "T", "turns": [{"speaker": "A", "text": "Hi."}, '
        '{"speaker": "B", "text": "Hello."}, {"speaker": "C", "text": "Also."}]}'
    )
    podcast.build(raw, voice)

    assert [turn.voice for turn in voice.turns] == ["lead", "guest", "lead"]


def test_podcast_without_a_voice_engine_never_calls_the_text_model(
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
        podcast.render(None, [], None)
