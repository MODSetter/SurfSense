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


def test_infographic_is_deterministic_escaped_svg() -> None:
    """Infographic facts become safe SVG and searchable markdown without an image API."""
    raw = (
        '{"title":"Saturn <script>","summary":"Rings",'
        '"sections":[{"label":"Count","value":"7","detail":"Main rings"}]}'
    )
    built = infographic.build(raw, [])

    assert built.primary_mime == "image/svg+xml"
    assert b"<script>" not in built.primary
    assert b"Saturn &lt;script&gt;" in built.primary
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
