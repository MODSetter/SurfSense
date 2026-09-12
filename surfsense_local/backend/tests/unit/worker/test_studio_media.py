"""Media formats: a podcast synthesised offline and a remote generated image."""

import pytest

from modules.llm.providers.protocols import GeneratedImage
from modules.llm.resolution import ModelResolutionError, ResolvedImageGeneration
from worker.studio.artifact import Source
from worker.studio.media import image, podcast

pytestmark = pytest.mark.unit

PNG = b"\x89PNG\r\n\x1a\nfake image bytes"


def test_render_stores_the_returned_png(monkeypatch: pytest.MonkeyPatch) -> None:
    """The selected ImageGenerator result becomes the artifact's primary file."""

    class FakeImageGenerator:
        async def generate(self, model: str, prompt: str) -> GeneratedImage:
            assert model == "flux"
            assert "Saturn" in prompt
            return GeneratedImage(PNG, "image/png")

    selection = type("Selection", (), {"name": "flux"})()
    monkeypatch.setattr(
        image,
        "resolve_image_generation",
        lambda _session: ResolvedImageGeneration(selection, FakeImageGenerator()),
    )
    built = image.render(None, [Source(1, "Saturn", "rings")], "make it bold")

    assert built.primary == PNG
    assert built.primary_mime == "image/png"
    assert built.primary_filename == "image.png"
    assert built.title == "make it bold"


def test_render_without_a_selection_fails_clearly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The worker re-checks role resolution rather than calling an arbitrary API."""

    def missing(_session):
        raise ModelResolutionError("no image model selected")

    monkeypatch.setattr(image, "resolve_image_generation", missing)
    with pytest.raises(RuntimeError, match="no image model selected"):
        image.render(None, [], None)


def test_podcast_voices_a_two_host_transcript(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The transcript is the searchable body; the synthesised WAV is the file."""
    monkeypatch.setattr(
        "worker.studio.media.podcast.tts.synthesize", lambda turns: b"RIFFfake"
    )
    raw = (
        '{"title": "Saturn", "turns": [{"speaker": "A", "text": "Hi."}, '
        '{"speaker": "B", "text": "Tell me more."}]}'
    )
    built = podcast.build(raw, [])

    assert built.primary == b"RIFFfake"
    assert built.primary_mime == "audio/wav"
    assert built.primary_filename == "saturn.wav"
    assert "**A:** Hi." in built.markdown
    assert "**B:** Tell me more." in built.markdown


def test_podcast_without_the_voice_pack_fails_clearly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A machine lacking Kokoro gets a clear reason, like the parser-pack path."""
    monkeypatch.setattr(
        "worker.studio.media.podcast.tts.missing_kokoro_files",
        lambda: ["kokoro-v1.0.onnx"],
    )
    raw = '{"title": "T", "turns": [{"speaker": "A", "text": "Hi."}]}'

    with pytest.raises(RuntimeError, match="Kokoro"):
        podcast.build(raw, [])
