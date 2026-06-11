"""Local Kokoro adapter: on-box synthesis, no network or per-segment cost.

Kokoro selects its language model by a single-letter ``lang_code``, so this
adapter maps the brief's BCP-47 tag to that code and caches one pipeline per
code (pipeline construction loads weights and is expensive). Pipelines run in a
thread pool because Kokoro is synchronous; the renderer caps how many segments
synthesise at once.
"""

from __future__ import annotations

import asyncio
import io
from typing import TYPE_CHECKING

from ..audio import SynthesizedAudio
from ..errors import TextToSpeechError
from ..port import TextToSpeech
from ..request import SynthesisRequest

if TYPE_CHECKING:
    from kokoro import KPipeline

# Kokoro emits 24 kHz mono PCM regardless of voice.
_SAMPLE_RATE = 24000

# BCP-47 primary subtag -> Kokoro language code. English defaults to American;
# the en-GB region override below switches it to British.
_LANG_CODE_BY_PRIMARY = {
    "en": "a",
    "es": "e",
    "fr": "f",
    "hi": "h",
    "it": "i",
    "ja": "j",
    "pt": "p",
    "zh": "z",
}


class KokoroTextToSpeech(TextToSpeech):
    """Synthesises segments with locally hosted Kokoro pipelines."""

    def __init__(self) -> None:
        self._pipelines: dict[str, KPipeline] = {}

    @property
    def container(self) -> str:
        return "wav"

    async def synthesize(self, request: SynthesisRequest) -> SynthesizedAudio:
        if not isinstance(request.voice, str):
            raise TextToSpeechError("Kokoro voices are named by string, not a mapping")

        pipeline = self._pipeline_for(request.language)
        loop = asyncio.get_event_loop()
        try:
            generator = await loop.run_in_executor(
                None,
                lambda: pipeline(
                    request.text,
                    voice=request.voice,
                    speed=request.speed,
                    split_pattern=r"\n+",
                ),
            )
            segments = [audio for _gs, _ps, audio in generator]
        except Exception as exc:
            raise TextToSpeechError(f"Kokoro synthesis failed: {exc}") from exc

        if not segments:
            raise TextToSpeechError("Kokoro produced no audio for the text")

        return SynthesizedAudio(
            data=_encode_wav(segments, _SAMPLE_RATE),
            container="wav",
            sample_rate=_SAMPLE_RATE,
        )

    def _pipeline_for(self, language: str) -> KPipeline:
        lang_code = _lang_code(language)
        pipeline = self._pipelines.get(lang_code)
        if pipeline is None:
            from kokoro import KPipeline

            pipeline = KPipeline(lang_code=lang_code)
            self._pipelines[lang_code] = pipeline
        return pipeline


def _lang_code(language: str) -> str:
    normalised = language.strip().lower()
    if normalised.startswith("en-gb") or normalised == "en-uk":
        return "b"
    primary = normalised.partition("-")[0]
    code = _LANG_CODE_BY_PRIMARY.get(primary)
    if code is None:
        raise TextToSpeechError(f"Kokoro has no language model for {language!r}")
    return code


def _encode_wav(segments: list, sample_rate: int) -> bytes:
    import numpy as np
    import soundfile as sf

    waveform = segments[0] if len(segments) == 1 else np.concatenate(segments)
    buffer = io.BytesIO()
    sf.write(buffer, waveform, sample_rate, format="WAV")
    return buffer.getvalue()
