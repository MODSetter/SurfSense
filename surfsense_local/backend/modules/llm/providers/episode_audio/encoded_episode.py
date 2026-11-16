"""The joined episode as MP3, about a sixth of its WAV, through LAME (lameenc).
WAV where lameenc is not installed or fails, so the episode is never lost."""

import io
import logging
import wave

from modules.llm.providers.protocols import SynthesizedAudio

__all__ = ["encoded_episode"]

logger = logging.getLogger(__name__)

# Per channel: speech at 24 kHz mono stays clear at 64 kbit/s.
KBPS_PER_CHANNEL = 64
# LAME's 0 (best) to 9 (fastest); 2 is its recommended near-best.
QUALITY = 2


def encoded_episode(wav: bytes) -> SynthesizedAudio:
    """`wav` is joined_wav's output; LAME takes 16-bit PCM only."""
    try:
        import lameenc
    except ImportError:
        logger.warning("lameenc is not installed; the episode stays WAV")
        return SynthesizedAudio(wav, "audio/wav")
    try:
        with wave.open(io.BytesIO(wav)) as pcm:
            channels, width, rate = (
                pcm.getnchannels(),
                pcm.getsampwidth(),
                pcm.getframerate(),
            )
            frames = pcm.readframes(pcm.getnframes())
    except (wave.Error, EOFError):
        logger.warning("the episode is not a WAV LAME can read; it stays as it is")
        return SynthesizedAudio(wav, "audio/wav")
    # LAME takes 16-bit samples only.
    if width != 2:
        return SynthesizedAudio(wav, "audio/wav")
    try:
        encoder = lameenc.Encoder()
        encoder.set_channels(channels)
        encoder.set_in_sample_rate(rate)
        encoder.set_bit_rate(KBPS_PER_CHANNEL * channels)
        encoder.set_quality(QUALITY)
        mp3 = bytes(encoder.encode(frames) + encoder.flush())
    except (RuntimeError, MemoryError):
        # The voices are paid for: keep the episode rather than fail a job
        # whose retry would voice, and bill, it again.
        logger.warning("MP3 encoding failed; the episode stays WAV", exc_info=True)
        return SynthesizedAudio(wav, "audio/wav")
    return SynthesizedAudio(mp3, "audio/mpeg")
