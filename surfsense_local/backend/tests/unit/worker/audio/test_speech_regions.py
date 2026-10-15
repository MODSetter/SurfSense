"""Where a decoded recording holds speech, as the window planner reads it: the
real Silero over the file a minute at a time, and all of it when Silero is not
there."""

from pathlib import Path

import pytest

from worker.audio_decode.decode import decode_to_pcm
from worker.ingestion.audio.speech_regions import hear_recording

pytestmark = pytest.mark.unit

# Three sentences voiced by Kokoro-82M through the app's podcast server, in
# English, Spanish and Portuguese, 3 s of silence between them: 36.65 s.
SPEECH = Path(__file__).resolve().parents[3] / "fixtures" / "audio" / "speech.ogg"
SILENCES = (14.0, 26.3)


def nothing() -> None:
    """A job nobody cancels."""


@pytest.fixture
def decoded(tmp_path: Path) -> Path:
    """The sentences as the decode child leaves them."""
    out = tmp_path / "audio16k.raw"
    assert decode_to_pcm(SPEECH, out).kind == "decoded"
    return out


def test_each_sentence_is_speech_and_the_pauses_are_not(
    decoded: Path, real_silero_vad
) -> None:
    """The silence between sentences falls between regions, never inside one."""
    heard = hear_recording(decoded, between_reads=nothing)

    assert heard.seconds == pytest.approx(36.65, abs=0.01)
    assert not any(r.start_s < at < r.end_s for r in heard.regions for at in SILENCES)
    assert sum(r.end_s - r.start_s for r in heard.regions) > 25.0


def test_a_silent_recording_holds_no_speech(tmp_path: Path, real_silero_vad) -> None:
    """What fails the recording with "No speech was found"."""
    silent = tmp_path / "audio16k.raw"
    silent.write_bytes(b"\0\0" * 16000 * 90)

    assert hear_recording(silent, between_reads=nothing).regions == []


def test_without_silero_all_of_it_is_speech(
    decoded: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A recording is never lost for want of the detector."""
    monkeypatch.setenv("SURFSENSE_LOCAL_MODELS_DIR", str(tmp_path / "no-models"))

    heard = hear_recording(decoded, between_reads=nothing)

    assert [(r.start_s, r.end_s) for r in heard.regions] == [(0.0, heard.seconds)]


def test_the_job_is_asked_between_reads(decoded: Path, tmp_path: Path) -> None:
    """A cancel lands while a long file is still being listened to."""

    class CancelError(Exception):
        pass

    def cancelled() -> None:
        raise CancelError

    with pytest.raises(CancelError):
        hear_recording(decoded, between_reads=cancelled)
