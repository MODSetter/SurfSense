"""The audio node synthesises in the deck's language, end to end.

This is the test that fails for the reason in the bug report: before the fix
the node called Kokoro with ``lang_code="a"`` and the voice ``af_heart`` no
matter what language the slides were written in. TTS is an external boundary
and is faked; everything between the graph state and the synthesis request is
the real code path.
"""

from __future__ import annotations

import pytest

from app.agents.video_presentation import nodes
from app.agents.video_presentation.state import SlideContent, State
from app.podcasts.tts import SynthesizedAudio

pytestmark = pytest.mark.unit


class _RecordingTts:
    """Stands in for the configured provider and records what it was asked for."""

    container = "wav"

    def __init__(self) -> None:
        self.requests = []

    async def synthesize(self, request):
        self.requests.append(request)
        return SynthesizedAudio(data=b"fake-audio", container="wav", sample_rate=24000)


@pytest.fixture
def recording_tts(monkeypatch, tmp_path):
    """Fake the provider and keep the node's scratch dirs inside tmp_path.

    ``create_slide_audio`` creates ``temp_audio/`` and
    ``video_presentation_audio/`` relative to the working directory, so the
    chdir is what stops the test from writing into the repo.
    """
    monkeypatch.chdir(tmp_path)
    fake = _RecordingTts()
    monkeypatch.setattr(nodes, "get_text_to_speech", lambda: fake)

    async def _duration(_path: str) -> float:
        return 3.0

    monkeypatch.setattr(nodes, "_get_audio_duration", _duration)
    return fake


def _one_slide() -> SlideContent:
    return SlideContent(
        slide_number=1,
        title="タイトル",
        subtitle="サブタイトル",
        content_in_markdown="## 見出し",
        speaker_transcripts=["これは日本語のナレーションです。"],
        background_explanation="Calm and precise",
    )


async def test_create_slide_audio_synthesises_in_the_slide_language(
    recording_tts, tts_service
):
    tts_service("local/kokoro")
    state = State(db_session=None, source_content="", slides=[_one_slide()])
    state.language = "ja"

    await nodes.create_slide_audio(state, {})

    assert len(recording_tts.requests) == 1
    request = recording_tts.requests[0]
    assert request.language == "ja"
    assert request.voice.startswith("j"), (
        f"expected a Japanese Kokoro voice, got {request.voice!r}"
    )


async def test_create_slide_audio_narrates_english_with_the_previous_voice(
    recording_tts, tts_service
):
    tts_service("local/kokoro")
    state = State(db_session=None, source_content="", slides=[_one_slide()])
    state.language = "en"

    await nodes.create_slide_audio(state, {})

    assert recording_tts.requests[0].voice == "af_heart"


async def test_create_slide_audio_uses_the_providers_container(
    recording_tts, tts_service
):
    """The output extension now comes from the adapter, not an inline branch."""
    tts_service("local/kokoro")
    state = State(db_session=None, source_content="", slides=[_one_slide()])
    state.language = "ja"

    result = await nodes.create_slide_audio(state, {})

    assert result["slide_audio_results"][0].audio_file.endswith(".wav")
