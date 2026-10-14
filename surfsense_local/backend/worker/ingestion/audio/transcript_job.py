"""A recording's transcript, as ingest's parse step: is speech recognition ready,
the file decoded in a child, where it holds speech, the windows that speech is
cut into, each window written down through the API, and the transcript.

Everything it keeps lives under the document's transcript/ folder; work/ holds
what a yield, a retry or a restart resumes from, and goes once the transcript
is done.
"""

import errno
import logging
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy.orm import Session, object_session

from modules.documents.models import Document
from modules.documents.recordings.layout import WorkFiles, segments_file, work_files
from modules.documents.recordings.metadata import AWAITING, KEY, is_awaiting
from modules.llm.model_route.api_address import api_url
from shared.config import get_storage_settings
from worker.audio_decode.room import needed_bytes
from worker.audio_decode.run import decode_in_child
from worker.ingestion.audio.checkpoint import DoneWindow, resumable_windows
from worker.ingestion.audio.failures import (
    NO_AUDIO,
    NO_SPEECH,
    UNDECODABLE,
    AwaitingSpeechModelError,
    RecordingRefusedError,
    no_room,
)
from worker.ingestion.audio.model_name import model_name
from worker.ingestion.audio.plan_file import Plan, read_plan, write_plan
from worker.ingestion.audio.queue_turn import QueueTurn
from worker.ingestion.audio.readiness import speech_recognition_ready
from worker.ingestion.audio.segments_file import write_segments
from worker.ingestion.audio.speech_regions import hear_recording
from worker.ingestion.audio.transcript_text import (
    HeardWindow,
    header_language,
    majority_language,
    transcript_markdown,
)
from worker.ingestion.audio.transcription_api import SpeechStatus, TranscriptionApi
from worker.ingestion.audio.window_loop import (
    ModelChangedError,
    RecordingWindows,
    transcribe_windows,
)
from worker.ingestion.audio.windows import plan_windows
from worker.jobs import JobYieldedError, merge_metadata

__all__ = ["recording_markdown"]

logger = logging.getLogger(__name__)


def recording_markdown(document: Document, original: Path) -> str:
    """Raises JobYieldedError to give the queue up, AwaitingSpeechModelError
    with no speech model, RecordingRefusedError for a recording that would fail
    the same way again, and RecordingFailedError for one worth another try."""
    # The ingest job's own session: cancel is checked, and metadata kept, on it.
    session = object_session(document)
    assert session is not None, "a recording is transcribed inside its ingest job"
    folder = get_storage_settings().document_dir(document.workspace_id, document.id)
    files = work_files(folder)
    turn = QueueTurn(session, document)
    if is_awaiting(document.document_metadata):
        merge_metadata(session, document, KEY, None)
    try:
        api = TranscriptionApi(api_url())
        status = speech_recognition_ready(api, turn)
        files.folder.mkdir(parents=True, exist_ok=True)
        return _transcribe(session, document, original, api, turn, folder, status)
    except JobYieldedError:
        raise
    except AwaitingSpeechModelError:
        merge_metadata(session, document, KEY, {AWAITING: True})
        _end_of_run(files)
        raise
    except BaseException:
        _end_of_run(files)
        raise


def _transcribe(
    session: Session,
    document: Document,
    original: Path,
    api: TranscriptionApi,
    turn: QueueTurn,
    folder: Path,
    status: SpeechStatus,
) -> str:
    assert status.model is not None, "a ready status names its model"
    files = work_files(folder)
    model_id, intent = status.model, status.language_intent
    while True:
        plan, done = _planned(original, files, turn, model_id, intent)
        with _full_disk_refused(plan.seconds):
            try:
                done = transcribe_windows(
                    RecordingWindows(
                        session, document, api, turn, files, plan, model_id, intent
                    ),
                    done,
                )
            except ModelChangedError as changed:
                files.windows.unlink(missing_ok=True)
                model_id = changed.model_id
                continue
            return _finished(session, document, folder, plan, done, model_id, status)


def _planned(
    original: Path, files: WorkFiles, turn: QueueTurn, model_id: str, intent: str
) -> tuple[Plan, dict[int, DoneWindow]]:
    """The windows, and those done already by this model for this language.
    The audio is decoded again only while windows remain to send."""
    plan = read_plan(files.plan)
    if plan is None:
        # A checkpoint of some other cut of the recording.
        files.windows.unlink(missing_ok=True)
        files.progress.unlink(missing_ok=True)
    done = resumable_windows(files.windows, model_id, intent)
    if plan is not None and len(done) == len(plan.windows):
        return plan, done
    if not files.audio.is_file():
        _decode(original, files.audio, turn)
    if plan is None:
        heard = hear_recording(files.audio, between_reads=turn.check_cancelled)
        if not heard.regions:
            raise RecordingRefusedError(NO_SPEECH)
        plan = Plan(
            heard.seconds, plan_windows(heard.regions, heard.levels, heard.frame_s)
        )
        with _full_disk_refused(plan.seconds):
            write_plan(files.plan, plan)
    return plan, done


def _decode(original: Path, audio: Path, turn: QueueTurn) -> None:
    outcome = decode_in_child(original, audio, between_polls=turn.check_cancelled)
    if outcome.kind == "no_room":
        raise no_room(outcome.needed_bytes)
    if outcome.kind == "no_audio":
        raise RecordingRefusedError(NO_AUDIO)
    if outcome.kind == "undecodable":
        logger.info("transcription: %s is undecodable: %s", original, outcome.detail)
        raise RecordingRefusedError(UNDECODABLE)


def _finished(
    session: Session,
    document: Document,
    folder: Path,
    plan: Plan,
    done: dict[int, DoneWindow],
    model_id: str,
    status: SpeechStatus,
) -> str:
    pinned = status.pinned_language
    heard = [
        HeardWindow(w.start_s, w.end_s, w.text, w.language)
        for _, w in sorted(done.items())
    ]
    if not any(window.text for window in heard):
        raise RecordingRefusedError(NO_SPEECH)
    language = pinned or majority_language(heard)
    markdown = transcript_markdown(
        title=document.title,
        seconds=plan.seconds,
        windows=heard,
        language=header_language(heard, pinned, status.languages),
        model=model_name(model_id),
    )
    write_segments(
        segments_file(folder),
        model_id=model_id,
        language=language,
        seconds=plan.seconds,
        windows=heard,
    )
    merge_metadata(
        session,
        document,
        KEY,
        {"language": language, "duration_s": round(plan.seconds, 3), "model": model_id},
    )
    shutil.rmtree(work_files(folder).folder, ignore_errors=True)
    return markdown


def _end_of_run(files: WorkFiles) -> None:
    """A run that ends the job keeps its windows and plan for the next one, not
    the decoded audio, which decoding again costs seconds to make."""
    files.audio.unlink(missing_ok=True)
    files.progress.unlink(missing_ok=True)


@contextmanager
def _full_disk_refused(seconds: float) -> Iterator[None]:
    try:
        yield
    except OSError as error:
        if error.errno == errno.ENOSPC:
            raise no_room(needed_bytes(seconds)) from error
        raise
