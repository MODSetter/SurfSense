"""A phrase or a window is taken only as the recogniser reads it: 16 kHz mono
16-bit PCM WAV, at most 30 s."""

import io
import wave

import pytest

from modules.llm.transcription.audio_checks import UnfitAudioError, checked_audio

pytestmark = pytest.mark.unit


def wav(
    seconds: float, *, rate: int = 16000, channels: int = 1, width: int = 2
) -> bytes:
    """A clip in the given format."""
    out = io.BytesIO()
    with wave.open(out, "wb") as clip:
        clip.setnchannels(channels)
        clip.setsampwidth(width)
        clip.setframerate(rate)
        clip.writeframes(b"\x01" * width * channels * int(seconds * rate))
    return out.getvalue()


def test_a_fitting_clip_is_taken_with_its_length() -> None:
    """Its length sets the request's deadline."""
    clip = checked_audio(wav(2.5))

    assert clip.seconds == 2.5
    assert len(clip.pcm) == 2.5 * 16000 * 2


def test_what_is_sent_on_is_a_wav_of_the_same_samples() -> None:
    """Written afresh, in the format the server reads."""
    clip = checked_audio(wav(1.0))

    with wave.open(io.BytesIO(clip.wav())) as sent:
        assert (sent.getframerate(), sent.getnchannels(), sent.getsampwidth()) == (
            16000,
            1,
            2,
        )
        assert sent.readframes(sent.getnframes()) == clip.pcm


def test_a_clip_cut_mid_sample_keeps_its_whole_samples() -> None:
    """Half a sample would fail the detector and reach the server as is."""
    clip = checked_audio(wav(1.0)[:-1])

    assert len(clip.pcm) == (16000 - 1) * 2


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(b"not audio at all", id="not a WAV"),
        pytest.param(wav(1.0, rate=44100), id="another rate"),
        pytest.param(wav(1.0, channels=2), id="stereo"),
        pytest.param(wav(1.0, width=1), id="8-bit"),
        pytest.param(wav(30.5), id="over 30 s"),
    ],
)
def test_anything_else_is_refused(data: bytes) -> None:
    """The composer and the worker both resample first."""
    with pytest.raises(UnfitAudioError):
        checked_audio(data)
