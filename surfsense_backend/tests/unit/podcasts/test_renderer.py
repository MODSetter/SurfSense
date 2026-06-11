"""The renderer refuses an inconsistent spec/transcript before spending work.

Full synthesis-and-merge needs FFmpeg and a real provider, so it belongs to an
integration test. What is pure and worth securing here is the renderer's
contract that it validates the transcript against the brief up front: a turn
naming an unknown speaker, or a speaker naming an unknown voice, fails loudly
rather than producing silent or wrong audio. The TTS provider is an external
port, faked here and never expected to be called on these paths.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.podcasts.rendering import PodcastRenderer, RenderError
from app.podcasts.schemas import (
    DurationTarget,
    PodcastSpec,
    SpeakerRole,
    SpeakerSpec,
    Transcript,
    TranscriptTurn,
)
from app.podcasts.tts import SynthesizedAudio
from app.podcasts.voices import CatalogVoice, TtsProvider, VoiceCatalog, VoiceGender

pytestmark = pytest.mark.unit


class _UnusedTTS:
    """A TTS port double that fails the test if it is ever asked to speak.

    These behaviors must short-circuit before synthesis, so any call here is a
    regression.
    """

    @property
    def container(self) -> str:
        return "mp3"

    async def synthesize(self, _request):  # pragma: no cover - must not run
        raise AssertionError("synthesis should not be attempted")
        return SynthesizedAudio(data=b"", container="mp3")


def _catalog_with(voice_id: str) -> VoiceCatalog:
    return VoiceCatalog(
        [
            CatalogVoice(
                voice_id=voice_id,
                provider=TtsProvider.KOKORO,
                language="en-US",
                display_name=voice_id,
                gender=VoiceGender.MALE,
                native_ref="am_adam",
            )
        ]
    )


def _spec(voice_id: str) -> PodcastSpec:
    return PodcastSpec(
        language="en",
        speakers=[
            SpeakerSpec(slot=0, name="Host", role=SpeakerRole.HOST, voice_id=voice_id)
        ],
        duration=DurationTarget(min_minutes=5, max_minutes=10),
    )


async def test_render_rejects_a_turn_for_an_unknown_speaker(tmp_path):
    renderer = PodcastRenderer(tts=_UnusedTTS(), catalog=_catalog_with("kokoro:am_adam"))
    transcript = Transcript(turns=[TranscriptTurn(speaker=5, text="Who am I?")])

    with pytest.raises(RenderError):
        await renderer.render(
            spec=_spec("kokoro:am_adam"), transcript=transcript, workdir=Path(tmp_path)
        )


async def test_render_rejects_a_speaker_whose_voice_is_not_in_the_catalog(tmp_path):
    renderer = PodcastRenderer(tts=_UnusedTTS(), catalog=_catalog_with("kokoro:am_adam"))
    transcript = Transcript(turns=[TranscriptTurn(speaker=0, text="Hello.")])

    with pytest.raises(RenderError):
        await renderer.render(
            spec=_spec("kokoro:ghost"), transcript=transcript, workdir=Path(tmp_path)
        )
