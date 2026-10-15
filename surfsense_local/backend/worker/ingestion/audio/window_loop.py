"""Every window the checkpoint lacks, sent to the API in turn: checked for cancel
first, appended to the checkpoint once written down, its progress kept and
announced, and the queue given up between windows when other sources wait."""

import time
from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path

from sqlalchemy.orm import Session

from modules.documents.models import Document
from modules.documents.recordings.layout import WorkFiles
from modules.documents.recordings.progress_file import (
    TranscriptionProgress,
    read_progress,
    write_progress,
)
from modules.events.schemas import Progress
from modules.llm.transcription.audio_checks import SAMPLE_RATE, wav_of
from worker.ingestion.audio.checkpoint import DoneWindow, append_window
from worker.ingestion.audio.failures import (
    ENGINE_STOPPED,
    AwaitingSpeechModelError,
    RecordingFailedError,
    RecordingRefusedError,
)
from worker.ingestion.audio.plan_file import Plan
from worker.ingestion.audio.queue_turn import QueueTurn
from worker.ingestion.audio.transcription_api import (
    NeedsSpeechModelError,
    TranscriptionApi,
    UnavailableError,
    WaitingError,
    WindowText,
)
from worker.ingestion.audio.waiting_work import another_recording_queued
from worker.notify import notify_document_updates

__all__ = ["ModelChangedError", "RecordingWindows", "transcribe_windows"]

# A server restart takes seconds; one that is down past these is a failure.
RETRY_DELAYS = (1, 2, 4, 8, 16)
# Memory waits are summed across yields; past this the recording fails.
MEMORY_WAIT_LIMIT_S = 600.0


class ModelChangedError(Exception):
    """Another speech model was chosen while this recording was transcribed:
    it starts over, so one model writes the whole transcript."""

    def __init__(self, model_id: str) -> None:
        super().__init__(model_id)
        self.model_id = model_id


@dataclass(frozen=True)
class RecordingWindows:
    session: Session
    document: Document
    api: TranscriptionApi
    turn: QueueTurn
    files: WorkFiles
    plan: Plan
    model_id: str
    intent: str


def transcribe_windows(
    job: RecordingWindows, done: dict[int, DoneWindow]
) -> dict[int, DoneWindow]:
    """Raises ModelChangedError, AwaitingSpeechModelError, a refusal once memory
    has been short for 10 minutes in all, and JobYieldedError or
    JobCancelledError from the turn."""
    final = len(job.plan.windows) - 1
    progress = _progress_so_far(job, done)
    for n, window in enumerate(job.plan.windows):
        if n in done:
            continue
        job.turn.check_cancelled()
        last = n == final and not another_recording_queued(job.session, job.document.id)
        pcm = _samples(job.files.audio, window.start_s, window.end_s)
        written, progress = _transcribed(job, pcm, last, progress)
        if written.model_id != job.model_id:
            raise ModelChangedError(written.model_id)
        done[n] = DoneWindow(
            n,
            window.start_s,
            window.end_s,
            written.text,
            written.language,
            job.model_id,
            job.intent,
        )
        append_window(job.files.windows, done[n])
        progress = replace(progress, done_s=window.end_s)
        write_progress(job.files.progress, progress)
        notify_document_updates(
            job.document, Progress(done_s=progress.done_s, total_s=progress.total_s)
        )
        if n != final:
            job.turn.give_way()
    return done


def _transcribed(
    job: RecordingWindows,
    pcm: bytes,
    last: bool,
    progress: TranscriptionProgress,
) -> tuple[WindowText, TranscriptionProgress]:
    seconds = len(pcm) / 2 / SAMPLE_RATE
    retries = iter(RETRY_DELAYS)
    while True:
        asked = time.monotonic()
        try:
            return job.api.transcribe(wav_of(pcm), seconds=seconds, last=last), progress
        except WaitingError as waiting:
            if waiting.reason == "memory":
                progress = _waited_for_memory(job, progress, asked, waiting)
        except UnavailableError:
            _pause_or_stop(retries)
        except NeedsSpeechModelError as error:
            raise AwaitingSpeechModelError from error
        job.turn.check_cancelled()
        job.turn.give_way()


def _waited_for_memory(
    job: RecordingWindows,
    progress: TranscriptionProgress,
    asked: float,
    waiting: WaitingError,
) -> TranscriptionProgress:
    waited = progress.memory_wait_s + time.monotonic() - asked
    progress = replace(progress, memory_wait_s=waited)
    write_progress(job.files.progress, progress)
    if waited > MEMORY_WAIT_LIMIT_S:
        # The API's sentence: "Transcribing needs about 2.9 GB free; ...".
        raise RecordingRefusedError(str(waiting))
    return progress


def _pause_or_stop(retries: Iterator[int]) -> None:
    delay = next(retries, None)
    if delay is None:
        raise RecordingFailedError(ENGINE_STOPPED)
    time.sleep(delay)


def _progress_so_far(
    job: RecordingWindows, done: dict[int, DoneWindow]
) -> TranscriptionProgress:
    """From the checkpoint, and the memory waits of the runs this one carries
    on from after a yield."""
    kept = read_progress(job.files.progress)
    return TranscriptionProgress(
        max((window.end_s for window in done.values()), default=0.0),
        job.plan.seconds,
        0.0 if kept is None else kept.memory_wait_s,
    )


def _samples(audio: Path, start_s: float, end_s: float) -> bytes:
    first = round(start_s * SAMPLE_RATE)
    count = round(end_s * SAMPLE_RATE) - first
    with audio.open("rb") as recording:
        recording.seek(first * 2)
        return recording.read(count * 2)
