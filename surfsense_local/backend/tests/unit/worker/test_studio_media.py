"""Media formats: a podcast synthesised offline, an image drawn by a BYO model."""

import base64

import pytest

from worker.studio.artifact import Source
from worker.studio.media import podcast, visual

pytestmark = pytest.mark.unit

PNG = b"\x89PNG\r\n\x1a\n fake image bytes"


def _reply(url: str) -> dict:
    return {"choices": [{"message": {"images": [{"image_url": {"url": url}}]}}]}


def test_render_stores_the_returned_png(monkeypatch: pytest.MonkeyPatch) -> None:
    """A data-URL image comes back decoded as the artifact's primary file."""
    data_url = "data:image/png;base64," + base64.b64encode(PNG).decode()
    monkeypatch.setattr(visual, "read_provider_key", lambda *a: "key")
    monkeypatch.setattr(visual, "_request_image", lambda key, content: _reply(data_url))

    built = visual.render(None, "image", [Source(1, "Saturn", "rings")], "make it bold")

    assert built.primary == PNG
    assert built.primary_mime == "image/png"
    assert built.primary_filename == "image.png"
    assert built.title == "make it bold"


def test_render_without_a_key_fails_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    """The API gates this, but the worker re-checks rather than 401 upstream."""
    monkeypatch.setattr(visual, "read_provider_key", lambda *a: None)

    with pytest.raises(RuntimeError, match="OpenRouter API key"):
        visual.render(None, "image", [], None)


def test_a_reply_with_no_image_is_an_error() -> None:
    """A text-only answer must fail the job, not save an empty file."""
    with pytest.raises(RuntimeError, match="no image"):
        visual._first_image({"choices": [{"message": {}}]})


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
