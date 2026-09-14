"""Media kinds: visual (a drawn image, a built SVG) and audio (a voiced podcast)."""

import pytest

from modules.llm.providers.protocols import GeneratedImage
from modules.llm.resolution import ResolvedImageGeneration
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


def test_podcast_voices_a_two_host_transcript(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The transcript is the searchable body; the synthesised WAV is the file."""
    monkeypatch.setattr(
        "worker.studio.media.audio.podcast.tts.synthesize", lambda turns: b"RIFFfake"
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
        "worker.studio.media.audio.podcast.tts.missing_kokoro_files",
        lambda: ["kokoro-v1.0.onnx"],
    )
    raw = '{"title": "T", "turns": [{"speaker": "A", "text": "Hi."}]}'

    with pytest.raises(RuntimeError, match="Kokoro"):
        podcast.build(raw, [])
