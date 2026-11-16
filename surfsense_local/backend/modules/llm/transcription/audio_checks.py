"""A phrase or a window as the recogniser reads it: 16 kHz mono 16-bit PCM WAV,
at most 30 s, checked with the standard library before anything is sent."""

import io
import wave
from dataclasses import dataclass

__all__ = [
    "MAX_WAV_BYTES",
    "SAMPLE_RATE",
    "CheckedAudio",
    "UnfitAudioError",
    "checked_audio",
    "wav_of",
]

SAMPLE_RATE = 16000
# Windows are cut at 28 s and phrases at 20; a request's memory grows with it.
MAX_SECONDS = 30.0
# Its samples, and room for a header and chunks the server never reads.
MAX_WAV_BYTES = int(MAX_SECONDS * SAMPLE_RATE * 2) + 64 * 1024


class UnfitAudioError(ValueError):
    """Not audio the recogniser reads; the message says what is wrong."""


@dataclass(frozen=True)
class CheckedAudio:
    # 16-bit little-endian mono samples at 16 kHz.
    pcm: bytes

    @property
    def seconds(self) -> float:
        return len(self.pcm) / 2 / SAMPLE_RATE

    def wav(self) -> bytes:
        """Written afresh, so no chunk the server does not read rides along."""
        return wav_of(self.pcm)


def checked_audio(data: bytes) -> CheckedAudio:
    try:
        with wave.open(io.BytesIO(data)) as clip:
            shape = (clip.getframerate(), clip.getnchannels(), clip.getsampwidth())
            pcm = clip.readframes(clip.getnframes())
    except (wave.Error, EOFError) as error:
        raise UnfitAudioError(f"not a PCM WAV file: {error}") from error
    if shape != (SAMPLE_RATE, 1, 2):
        rate, channels, width = shape
        raise UnfitAudioError(
            f"needs 16 kHz mono 16-bit audio, not {rate} Hz, "
            f"{channels} channels, {width * 8}-bit"
        )
    # A file cut mid-sample keeps its whole samples.
    checked = CheckedAudio(pcm[: len(pcm) - len(pcm) % 2])
    if checked.seconds > MAX_SECONDS:
        raise UnfitAudioError(
            f"at most {MAX_SECONDS:.0f} s, not {checked.seconds:.1f} s"
        )
    return checked


def wav_of(pcm: bytes) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as clip:
        clip.setnchannels(1)
        clip.setsampwidth(2)
        clip.setframerate(SAMPLE_RATE)
        clip.writeframes(pcm)
    return out.getvalue()
