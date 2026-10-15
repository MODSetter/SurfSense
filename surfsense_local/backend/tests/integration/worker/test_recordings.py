"""A recording through ingest: decoded in a child, cut into windows, each window
written down through a stand-in of the API's routes, and the transcript
indexed. Without a staged Silero all of a recording counts as speech, so the
plan here is cut by loudness alone: the sentences' pause makes two windows."""

import io
import json
import wave
from collections.abc import Iterator
from pathlib import Path

import pytest
from huey.exceptions import CancelExecution
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.recordings.layout import segments_file, work_files
from modules.documents.schemas import DocumentRead
from modules.documents.tasks import PRIORITY_BULK, ingest_document
from modules.workspaces.models import Workspace
from shared.config import get_storage_settings
from shared.db import create_session_factory
from shared.queue import ingest_queue
from tests.integration.worker.speech_api_stand_in import MODEL, SpeechApi
from worker.audio_decode.outcome import DecodeOutcome
from worker.ingestion import run
from worker.ingestion.audio import queue_turn, readiness, transcript_job, window_loop

pytestmark = pytest.mark.integration

# Three sentences voiced by Kokoro-82M, 3 s of silence between them: 36.65 s.
SPEECH = Path(__file__).resolve().parents[2] / "fixtures" / "audio" / "speech.ogg"
HEADER = (
    "Transcript of standup.ogg · 0:36 · English (detected) · "
    "Nemotron 3.5 ASR Streaming 0.6B. [hh:mm:ss] marks where each passage starts."
)


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session on the migrated database ingest opens again by path."""
    with create_session_factory(engine)() as opened:
        yield opened


@pytest.fixture(autouse=True)
def quick_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """The waits between a dropped server's retries, cut for the test."""
    monkeypatch.setattr(window_loop, "RETRY_DELAYS", (0, 0, 0, 0, 0))
    monkeypatch.setattr(readiness, "POLL_SECONDS", 0.0)


def add_recording(
    session: Session,
    name: str = "standup.ogg",
    content: bytes | None = None,
    status: DocumentStatus = DocumentStatus.PENDING,
) -> Document:
    """A recording as the upload route leaves it: a pending row, its file alone
    in its folder."""
    workspace = session.scalar(text("SELECT id FROM workspaces LIMIT 1"))
    if workspace is None:
        created = Workspace(name="Standups")
        session.add(created)
        session.flush()
        workspace = created.id
    suffix = Path(name).suffix
    mime = {".ogg": "audio/ogg", ".wav": "audio/wav", ".mp3": "audio/mpeg"}[suffix]
    data = SPEECH.read_bytes() if content is None else content
    document = Document(
        workspace_id=workspace,
        title=name,
        document_type=DocumentType.FILE,
        status=status,
        document_metadata={
            "mime_type": mime,
            "size_bytes": len(data),
            "suffix": suffix,
        },
    )
    session.add(document)
    session.commit()
    folder = folder_of(document)
    folder.mkdir(parents=True)
    (folder / name).write_bytes(data)
    return document


def folder_of(document: Document) -> Path:
    """The recording's own folder, where its original and transcript/ live."""
    return get_storage_settings().document_dir(document.workspace_id, document.id)


def silent_wav(seconds: float) -> bytes:
    """Seconds of digital silence, as a 16 kHz memo."""
    out = io.BytesIO()
    with wave.open(out, "wb") as clip:
        clip.setnchannels(1)
        clip.setsampwidth(2)
        clip.setframerate(16000)
        clip.writeframes(b"\0\0" * int(seconds * 16000))
    return out.getvalue()


def checkpoint(document: Document) -> list[dict]:
    """The windows a run kept for the next."""
    path = work_files(folder_of(document)).windows
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def refused(document_id: int) -> None:
    """Ingest as Huey runs it, for a recording that is not tried again."""
    with pytest.raises(CancelExecution):
        ingest_document.call_local(document_id)


# Transcribed


def test_a_recording_becomes_a_timestamped_transcript(
    session: Session, stub_model: None, speech_api: SpeechApi
) -> None:
    """One header line, a paragraph per window from its time, and searchable."""
    recording = add_recording(session)

    run(recording.id)

    session.expire_all()
    assert recording.status is DocumentStatus.READY
    paragraphs = recording.content.split("\n\n")
    assert paragraphs[0] == HEADER
    assert paragraphs[1] == "[00:00:00] Words of window 0."
    assert paragraphs[2].startswith("[00:00:2")
    assert paragraphs[2].endswith("Words of window 1.\n")
    assert session.scalar(text("SELECT count(*) FROM chunks")) >= 1


def test_each_window_is_16_khz_mono_and_at_most_28_seconds(
    session: Session, stub_model: None, speech_api: SpeechApi
) -> None:
    """What the server reads; only the last tells the API the model may go."""
    run(add_recording(session).id)

    assert len(speech_api.windows) == 2
    assert all(w.seconds <= 28.0 for w in speech_api.windows)
    assert {(w.rate, w.channels) for w in speech_api.windows} == {(16000, 1)}
    assert [w.last for w in speech_api.windows] == [False, True]
    assert sum(w.seconds for w in speech_api.windows) == pytest.approx(36.65, abs=0.1)


def test_a_finished_recording_keeps_its_language_length_model_and_segments(
    session: Session, stub_model: None, speech_api: SpeechApi
) -> None:
    """The row says what was heard; segments.json where; work/ is gone and the
    original is still the only file beside the transcript."""
    recording = add_recording(session)

    run(recording.id)

    session.expire_all()
    assert recording.document_metadata["transcription"] == {
        "language": "en",
        "duration_s": pytest.approx(36.65, abs=0.01),
        "model": MODEL,
    }
    assert DocumentRead.model_validate(recording).transcription.model_dump() == {
        "language": "en",
        "progress": None,
        "awaiting": False,
    }
    segments = json.loads(segments_file(folder_of(recording)).read_text("utf-8"))
    assert segments["model_id"] == MODEL
    assert [w["line"] for w in segments["windows"]] == [3, 5]
    assert not work_files(folder_of(recording)).folder.exists()
    assert [p.name for p in folder_of(recording).iterdir() if p.is_file()] == [
        "standup.ogg"
    ]


def test_each_window_moves_the_rows_progress(
    session: Session, stub_model: None, speech_api: SpeechApi
) -> None:
    """A notice per window carries how far it has come, the last one all of it."""
    recording = add_recording(session)

    run(recording.id)

    progress = [e["progress"] for e in speech_api.events if "progress" in e]
    assert len(progress) == 2
    assert progress[0]["done_s"] < progress[1]["done_s"]
    assert progress[1] == {
        "done_s": pytest.approx(36.65, abs=0.01),
        "total_s": pytest.approx(36.65, abs=0.01),
    }
    assert all(e["ids"] == [recording.id] for e in speech_api.events)


def test_a_language_the_user_set_heads_the_transcript_without_detected(
    session: Session, stub_model: None, speech_api: SpeechApi
) -> None:
    """The intent is never rewritten from a detection."""
    speech_api.status["language_intent"] = "ja"
    speech_api.language = "en"
    recording = add_recording(session)

    run(recording.id)

    session.expire_all()
    assert " · Japanese · " in recording.content.split("\n", 1)[0]
    assert recording.document_metadata["transcription"]["language"] == "ja"


# Waiting for a speech model


def test_with_no_speech_model_the_recording_waits_for_one(
    session: Session, stub_model: None, speech_api: SpeechApi
) -> None:
    """Not an error the person must fix by uploading again: choosing a model
    queues it. Nothing is decoded before a model is there."""
    speech_api.status = {
        "ready": False,
        "reason": "needs_speech_model",
        "model": None,
        "language_intent": "auto",
        "languages": [],
    }
    recording = add_recording(session)

    refused(recording.id)

    session.expire_all()
    assert recording.status is DocumentStatus.FAILED
    assert recording.error_message == "Waiting for a speech model."
    assert DocumentRead.model_validate(recording).transcription.awaiting is True
    assert speech_api.windows == []
    assert not work_files(folder_of(recording)).audio.exists()


def test_a_model_deleted_between_windows_waits_and_resumes_where_it_stopped(
    session: Session, stub_model: None, speech_api: SpeechApi
) -> None:
    """The windows written stay for when a model is chosen again."""
    speech_api.replies = [
        (200, speech_api.written(0)),
        SpeechApi.refused(409, "needs_speech_model"),
    ]
    recording = add_recording(session)

    refused(recording.id)

    session.expire_all()
    assert DocumentRead.model_validate(recording).transcription.awaiting is True
    assert [w["n"] for w in checkpoint(recording)] == [0]

    speech_api.replies = []
    speech_api.windows.clear()
    session.commit()  # the reads above hold the write lock
    run(recording.id)

    session.expire_all()
    assert recording.status is DocumentStatus.READY
    assert len(speech_api.windows) == 1
    assert "awaiting" not in recording.document_metadata["transcription"]


# Yielding


def test_after_a_minute_a_recording_gives_way_to_a_waiting_note(
    session: Session,
    stub_model: None,
    speech_api: SpeechApi,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Back to pending and queued behind it, with what it has done kept: a
    note added midway is read within a window."""
    monkeypatch.setattr(queue_turn, "YIELD_AFTER_SECONDS", 0.0)
    recording = add_recording(session)
    session.add(
        Document(
            workspace_id=recording.workspace_id,
            title="Note",
            document_type=DocumentType.NOTE,
            content="text",
        )
    )
    session.commit()

    run(recording.id)

    session.expire_all()
    assert recording.status is DocumentStatus.PENDING
    assert [(t.name, t.args, t.priority) for t in ingest_queue.pending()] == [
        ("ingest_document", (recording.id,), PRIORITY_BULK)
    ]
    progress = DocumentRead.model_validate(recording).transcription.progress
    assert 0 < progress.done_s < progress.total_s
    assert len(speech_api.windows) == 1
    session.commit()  # the reads above hold the write lock

    run(recording.id)

    session.expire_all()
    assert recording.status is DocumentStatus.READY
    assert len(speech_api.windows) == 2


def test_recordings_never_give_way_to_each_other(
    session: Session,
    stub_model: None,
    speech_api: SpeechApi,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two queued recordings would only trade places; the speech model stays
    for the next one."""
    monkeypatch.setattr(queue_turn, "YIELD_AFTER_SECONDS", 0.0)
    recording = add_recording(session)
    add_recording(session, name="retro.ogg")

    run(recording.id)

    session.expire_all()
    assert recording.status is DocumentStatus.READY
    assert [w.last for w in speech_api.windows] == [False, False]


def test_a_cancel_during_a_window_stops_the_recording_after_it(
    session: Session, stub_model: None, speech_api: SpeechApi
) -> None:
    """The window in flight finishes; no other is sent, and the decoded audio
    goes while the windows written stay for a retry."""
    recording = add_recording(session)

    def cancel(n: int) -> None:
        with create_session_factory(session.get_bind())() as api:
            api.get(Document, recording.id).status = DocumentStatus.CANCELLED
            api.commit()

    speech_api.during_window = cancel

    run(recording.id)

    session.expire_all()
    assert recording.status is DocumentStatus.CANCELLED
    assert len(speech_api.windows) == 1
    assert [w["n"] for w in checkpoint(recording)] == [0]
    assert not work_files(folder_of(recording)).audio.exists()


def test_a_cancel_that_lands_as_the_recording_would_give_way_still_stops_it(
    session: Session,
    stub_model: None,
    speech_api: SpeechApi,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancelled, not queued again, and its decoded audio gone with it."""
    monkeypatch.setattr(queue_turn, "YIELD_AFTER_SECONDS", 0.0)
    recording = add_recording(session)
    session.add(
        Document(
            workspace_id=recording.workspace_id,
            title="Note",
            document_type=DocumentType.NOTE,
            content="text",
        )
    )
    session.commit()

    def cancel(n: int) -> None:
        with create_session_factory(session.get_bind())() as api:
            api.get(Document, recording.id).status = DocumentStatus.CANCELLED
            api.commit()

    speech_api.during_window = cancel

    run(recording.id)

    session.expire_all()
    assert recording.status is DocumentStatus.CANCELLED
    assert ingest_queue.pending() == []
    assert not work_files(folder_of(recording)).audio.exists()


# Failures


def test_a_retry_carries_on_from_the_windows_already_written(
    session: Session, stub_model: None, speech_api: SpeechApi
) -> None:
    """A server down past its retries fails the run, and Huey's next run sends
    only what is left."""
    speech_api.replies = [(200, speech_api.written(0))] + [
        SpeechApi.refused(503, "transcription_unavailable")
    ] * 6
    recording = add_recording(session)

    with pytest.raises(Exception, match="The speech recognition engine stopped"):
        ingest_document.call_local(recording.id)

    session.expire_all()
    assert recording.status is DocumentStatus.FAILED
    assert recording.error_message == "The speech recognition engine stopped."

    speech_api.replies = []
    speech_api.windows.clear()
    session.commit()  # the reads above hold the write lock
    run(recording.id)

    session.expire_all()
    assert recording.status is DocumentStatus.READY
    assert len(speech_api.windows) == 1


def test_a_restarting_server_or_a_dictation_only_delays_a_window(
    session: Session, stub_model: None, speech_api: SpeechApi
) -> None:
    """A dropped connection is asked again, and a dictation's turn waited out."""
    speech_api.replies = [
        SpeechApi.refused(503, "transcription_unavailable"),
        SpeechApi.waiting("dictation"),
        SpeechApi.waiting("hold"),
    ]
    recording = add_recording(session)

    run(recording.id)

    session.expire_all()
    assert recording.status is DocumentStatus.READY
    assert len(speech_api.windows) == 5


def test_ten_minutes_short_of_memory_fails_with_the_apis_sentence(
    session: Session,
    stub_model: None,
    speech_api: SpeechApi,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Summed across yields; the person reads what to free."""
    monkeypatch.setattr(window_loop, "MEMORY_WAIT_LIMIT_S", 0.0)
    sentence = "Transcribing needs about 2.9 GB free; this computer has 1.8 GB."
    speech_api.replies = [SpeechApi.waiting("memory", sentence)]
    recording = add_recording(session)

    refused(recording.id)

    session.expire_all()
    assert recording.error_message == sentence


def test_a_server_down_for_two_minutes_fails_and_is_tried_again(
    session: Session,
    stub_model: None,
    speech_api: SpeechApi,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In the seconds after a choice or a crash it is waited for, not longer."""
    monkeypatch.setattr(readiness, "GIVE_UP_SECONDS", 0.0)
    speech_api.status = {
        **speech_api.status,
        "ready": False,
        "reason": "transcription_unavailable",
    }
    recording = add_recording(session)

    with pytest.raises(Exception, match="The speech recognition engine stopped"):
        ingest_document.call_local(recording.id)

    session.expire_all()
    assert recording.status is DocumentStatus.FAILED


def test_a_recording_with_no_speech_fails_without_a_retry(
    session: Session, stub_model: None, speech_api: SpeechApi, real_silero_vad
) -> None:
    """Silence is not a transcript; nothing reaches the model."""
    recording = add_recording(session, name="silence.wav", content=silent_wav(40))

    refused(recording.id)

    session.expire_all()
    assert recording.error_message == "No speech was found in this recording."
    assert speech_api.windows == []


def test_a_file_with_no_audio_fails_without_a_retry(
    session: Session, stub_model: None, speech_api: SpeechApi
) -> None:
    """A header and no samples."""
    recording = add_recording(session, name="empty.wav", content=silent_wav(0))

    refused(recording.id)

    session.expire_all()
    assert recording.error_message == "This file has no audio."


def test_a_file_the_decoder_cannot_read_fails_without_a_retry(
    session: Session, stub_model: None, speech_api: SpeechApi
) -> None:
    """The same bytes would fail the same way; the worker lives on."""
    recording = add_recording(
        session, name="broken.mp3", content=b"ID3\x04" + bytes(range(256)) * 8
    )

    refused(recording.id)

    session.expire_all()
    assert recording.error_message == "This recording could not be decoded."


def test_a_disk_without_room_fails_with_what_it_needs(
    session: Session,
    stub_model: None,
    speech_api: SpeechApi,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Checked by the decoder from the file's own length before it writes."""
    monkeypatch.setattr(
        transcript_job,
        "decode_in_child",
        lambda *_a, **_k: DecodeOutcome("no_room", needed_bytes=2_460_000_000),
    )
    recording = add_recording(session)

    refused(recording.id)

    session.expire_all()
    assert recording.error_message == (
        "Transcribing needs about 2.5 GB of free disk space."
    )


def test_another_model_chosen_midway_writes_the_whole_transcript(
    session: Session, stub_model: None, speech_api: SpeechApi
) -> None:
    """One model's text is never stitched to another's. The new model starts
    without the language set for the last, so the header says what it heard."""
    speech_api.status["language_intent"] = "ja"
    other = {"text": "Other words.", "language": "en", "model_id": "other-model"}

    def choose_another(n: int) -> None:
        if n == 1:
            speech_api.status = {
                **speech_api.status,
                "model": "other-model",
                "language_intent": "auto",
            }

    speech_api.during_window = choose_another
    speech_api.replies = [(200, speech_api.written(0))] + [(200, other)] * 3
    recording = add_recording(session)

    run(recording.id)

    session.expire_all()
    assert recording.document_metadata["transcription"] == {
        "language": "en",
        "duration_s": pytest.approx(36.65, abs=0.01),
        "model": "other-model",
    }
    assert "Words of window 0." not in recording.content
    assert " · English (detected) · other-model." in recording.content.split("\n")[0]
    assert len(speech_api.windows) == 4
