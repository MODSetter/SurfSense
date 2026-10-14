"""The real Silero model over clips with no speech in them. Speech itself is
voiced by Kokoro in tests/packaging/test_audiocpp_transcription.py."""

import numpy as np
import pytest

from modules.llm.transcription.voice_activity.speech_spans import speech_spans

pytestmark = pytest.mark.unit

RATE = 16000


def pcm(samples: np.ndarray) -> bytes:
    """Float samples as the 16-bit PCM a phrase carries."""
    return (np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()


def test_silence_holds_no_speech(real_silero_vad) -> None:
    """A phrase cut from a pause never reaches the model."""
    assert speech_spans(pcm(np.zeros(3 * RATE))) == []


def test_steady_noise_holds_no_speech(real_silero_vad) -> None:
    """A fan or a hum under the mic."""
    noise = np.random.default_rng(7).normal(0, 0.05, 3 * RATE)
    tone = 0.2 * np.sin(2 * np.pi * 120 * np.arange(3 * RATE) / RATE)

    assert speech_spans(pcm(noise)) == []
    assert speech_spans(pcm(tone)) == []


def test_without_the_model_every_clip_counts_as_speech(tmp_path, monkeypatch) -> None:
    """Fail-open: no clip is dropped because the detector is missing."""
    monkeypatch.setenv("SURFSENSE_LOCAL_MODELS_DIR", str(tmp_path))

    assert speech_spans(pcm(np.zeros(RATE))) is None
