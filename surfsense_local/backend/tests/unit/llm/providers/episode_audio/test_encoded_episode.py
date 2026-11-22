"""A podcast episode as MP3, or the WAV it came as whenever that cannot be done."""

import io
import sys
import wave

import pytest

from modules.llm.providers.episode_audio.encoded_episode import encoded_episode

pytestmark = pytest.mark.unit


def wav(seconds: float = 2.0, rate: int = 24000) -> bytes:
    """A voice's joined episode: 16-bit mono PCM."""
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x01\x00" * int(rate * seconds))
    return out.getvalue()


def test_an_episode_is_mp3_at_its_own_rate() -> None:
    """About a sixth of the WAV, and the browser plays it as it did the WAV."""
    audio = encoded_episode(wav())

    assert audio.media_type == "audio/mpeg"
    header = audio.content[:4]
    assert header[0] == 0xFF and header[1] & 0xE0 == 0xE0, "an MPEG frame first"
    # MPEG-2's rate index 1 is 24 kHz, mono is channel mode 3.
    assert (header[1] >> 3 & 0b11, header[2] >> 2 & 0b11) == (0b10, 1)
    assert header[3] >> 6 == 0b11
    assert len(audio.content) < len(wav()) / 4


def test_without_lameenc_the_episode_stays_wav(monkeypatch) -> None:
    """A checkout that skipped the dependency still gets an episode it can play."""
    monkeypatch.setitem(sys.modules, "lameenc", None)

    audio = encoded_episode(wav())

    assert (audio.media_type, audio.content[:4]) == ("audio/wav", b"RIFF")


@pytest.mark.parametrize("raised", [RuntimeError, MemoryError])
def test_an_episode_the_encoder_fails_on_stays_wav(monkeypatch, raised) -> None:
    """The voices are paid for by then: the episode is kept, not failed and voiced again."""
    import lameenc

    class Broken:
        def __getattr__(self, name: str):
            def fail(*args: object) -> None:
                raise raised("lame_encode_buffer failed")

            return fail

    monkeypatch.setattr(lameenc, "Encoder", Broken)
    episode = wav()

    audio = encoded_episode(episode)

    assert (audio.media_type, audio.content) == ("audio/wav", episode)


def test_bytes_that_are_not_a_wav_are_left_as_they_are() -> None:
    """Nothing to encode from, so nothing is lost either."""
    audio = encoded_episode(b"RIFFfake")

    assert (audio.media_type, audio.content) == ("audio/wav", b"RIFFfake")
