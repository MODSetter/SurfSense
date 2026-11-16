"""The decode child as the ingest worker runs it: worker.py --decode-audio, a
process of its own whose death never reaches the consumer."""

import io
import struct
import sys
import wave
from pathlib import Path

import pytest

from worker.audio_decode import run as decode_run
from worker.audio_decode.run import decode_in_child

pytestmark = pytest.mark.integration

TONES = Path(__file__).resolve().parents[2] / "fixtures" / "audio"


class CancelError(Exception):
    """What a job's cancel check raises."""


def nothing() -> None:
    """A job nobody cancels."""


def long_wav(seconds: float) -> bytes:
    """Enough 44.1 kHz stereo audio for the decode to outlast a poll."""
    frame = struct.pack("<hh", 3000, -3000)
    out = io.BytesIO()
    with wave.open(out, "wb") as clip:
        clip.setnchannels(2)
        clip.setsampwidth(2)
        clip.setframerate(44100)
        clip.writeframes(frame * int(seconds * 44100))
    return out.getvalue()


def test_the_child_leaves_the_whole_recording_at_16_khz(tmp_path: Path) -> None:
    """Named `out` only once every sample is written."""
    out = tmp_path / "audio16k.raw"

    outcome = decode_in_child(TONES / "tone.ogg", out, between_polls=nothing)

    assert outcome.kind == "decoded"
    assert out.stat().st_size == pytest.approx(16000 * 2, rel=0.05)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["audio16k.raw"]


def test_a_file_the_child_refuses_says_why(tmp_path: Path) -> None:
    """Undecodable bytes come back as an outcome, not a crash of the worker."""
    source = tmp_path / "broken.flac"
    source.write_bytes(b"fLaC" + b"\xff" * 512)
    out = tmp_path / "audio16k.raw"

    outcome = decode_in_child(source, out, between_polls=nothing)

    assert outcome.kind == "undecodable"
    assert not out.exists()


def test_a_decoder_that_dies_is_an_undecodable_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A malformed file can take the decoder down with it; the job reads that
    as bytes it cannot read, and nothing is left half written."""
    out = tmp_path / "audio16k.raw"
    (tmp_path / "audio16k.raw.part").write_bytes(b"\0" * 64)
    monkeypatch.setattr(
        decode_run,
        "_command",
        lambda _source, _out: [sys.executable, "-c", "import os; os._exit(70)"],
    )

    outcome = decode_in_child(TONES / "tone.mp3", out, between_polls=nothing)

    assert outcome.kind == "undecodable"
    assert list(tmp_path.iterdir()) == []


def test_a_cancel_stops_the_child_and_leaves_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The job's cancel check runs while the child decodes, and wins."""
    monkeypatch.setattr(decode_run, "POLL_SECONDS", 0.01)
    source = tmp_path / "long.wav"
    source.write_bytes(long_wav(120))
    out = tmp_path / "audio16k.raw"

    def cancelled() -> None:
        raise CancelError

    with pytest.raises(CancelError):
        decode_in_child(source, out, between_polls=cancelled)

    assert sorted(p.name for p in tmp_path.iterdir()) == ["long.wav"]
