"""A recording read into 16 kHz mono 16-bit PCM, as the decode child does it,
and what it reports when it cannot: no room on disk, no audio, bytes the
decoder cannot read."""

import io
import math
import shutil
import struct
import wave
from collections import namedtuple
from pathlib import Path

import pytest

from worker.audio_decode.decode import decode_to_pcm
from worker.audio_decode.room import needed_bytes

pytestmark = pytest.mark.unit

# Made with ffmpeg from a 440 Hz tone, stereo at 44.1 kHz.
AUDIO = Path(__file__).resolve().parents[3] / "fixtures" / "audio"
RATE = 16000


def tone_wav(seconds: float, rate: int = 44100, channels: int = 2) -> bytes:
    """A 440 Hz tone as a WAV file, at a rate the recogniser does not take."""
    frames = b"".join(
        struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * n / rate))) * channels
        for n in range(int(seconds * rate))
    )
    out = io.BytesIO()
    with wave.open(out, "wb") as clip:
        clip.setnchannels(channels)
        clip.setsampwidth(2)
        clip.setframerate(rate)
        clip.writeframes(frames)
    return out.getvalue()


def samples(path: Path) -> list[int]:
    """The decoded file's samples."""
    data = path.read_bytes()
    return list(struct.unpack(f"<{len(data) // 2}h", data))


@pytest.mark.parametrize(
    ("name", "seconds"),
    [("tone.mp3", 1.0), ("tone.flac", 0.5), ("tone.ogg", 1.0)],
)
def test_each_format_becomes_16_khz_mono(
    tmp_path: Path, name: str, seconds: float
) -> None:
    """MP3, FLAC and Ogg Vorbis at 44.1 kHz stereo, down to what the server reads."""
    out = tmp_path / "audio16k.raw"

    outcome = decode_to_pcm(AUDIO / name, out)

    assert outcome.kind == "decoded"
    assert outcome.seconds == pytest.approx(seconds, rel=0.05)
    decoded = samples(out)
    assert len(decoded) == pytest.approx(seconds * RATE, rel=0.05)
    assert max(abs(s) for s in decoded) > 1000


def test_a_wave_file_at_another_rate_is_resampled(tmp_path: Path) -> None:
    """A 44.1 kHz stereo memo keeps its length at 16 kHz."""
    source = tmp_path / "memo.wav"
    source.write_bytes(tone_wav(2.0))
    out = tmp_path / "audio16k.raw"

    outcome = decode_to_pcm(source, out)

    assert (outcome.kind, len(samples(out))) == ("decoded", 2 * RATE)


def test_a_file_with_no_samples_has_no_audio(tmp_path: Path) -> None:
    """A header and nothing after it: nothing to transcribe, and no file left."""
    source = tmp_path / "empty.wav"
    source.write_bytes(tone_wav(0.0))
    out = tmp_path / "audio16k.raw"

    outcome = decode_to_pcm(source, out)

    assert outcome.kind == "no_audio"
    assert list(tmp_path.iterdir()) == [source]


def test_bytes_the_decoder_cannot_read_are_undecodable(tmp_path: Path) -> None:
    """Refused for good: the same bytes fail the same way again."""
    source = tmp_path / "broken.mp3"
    source.write_bytes(b"ID3\x04" + bytes(range(256)) * 8)
    out = tmp_path / "audio16k.raw"

    outcome = decode_to_pcm(source, out)

    assert outcome.kind == "undecodable"
    assert list(tmp_path.iterdir()) == [source]


@pytest.mark.parametrize("name", ["tone.mp3", "tone.ogg"])
def test_a_disk_without_room_for_the_decoded_audio_is_refused_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """Checked from the file's own length before a byte is written."""
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(shutil, "disk_usage", lambda _path: usage(1, 1, 10_000))
    out = tmp_path / "audio16k.raw"

    outcome = decode_to_pcm(AUDIO / name, out)

    assert (outcome.kind, outcome.needed_bytes) == ("no_room", needed_bytes(1.0))
    assert not out.exists()


@pytest.mark.parametrize(
    ("fixture", "name"),
    [
        ("tone.mp3", "réunion.mp3"),
        ("tone.flac", "会議.flac"),
        ("tone.ogg", "会議.ogg"),
        ("tone.ogg", "Besprechung für Jürgen.oga"),
    ],
)
def test_a_recording_named_in_any_script_decodes(
    tmp_path: Path, fixture: str, name: str
) -> None:
    """A file called 会議.ogg, or a data folder under a Windows account named
    José: no format may be refused for its path."""
    folder = tmp_path / "José"
    folder.mkdir()
    source = folder / name
    source.write_bytes((AUDIO / fixture).read_bytes())

    outcome = decode_to_pcm(source, folder / "audio16k.raw")

    assert outcome.kind == "decoded", outcome


def test_an_hour_needs_its_pcm_and_some_room_to_spare() -> None:
    """115.2 MB an hour at 16 kHz 16-bit mono, plus 64 MiB."""
    assert needed_bytes(3600) == 115_200_000 + 64 * 2**20
