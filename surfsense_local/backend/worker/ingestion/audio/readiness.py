"""Before anything is decoded: is a speech model chosen, and is its server up?
In the seconds after a model is chosen, or after a crash, it is not yet."""

import time

from worker.ingestion.audio.failures import (
    ENGINE_STOPPED,
    AwaitingSpeechModelError,
    RecordingFailedError,
)
from worker.ingestion.audio.queue_turn import QueueTurn
from worker.ingestion.audio.transcription_api import (
    SpeechStatus,
    TranscriptionApi,
    UnavailableError,
)

__all__ = ["speech_recognition_ready"]

POLL_SECONDS = 5.0
GIVE_UP_SECONDS = 120.0


def speech_recognition_ready(api: TranscriptionApi, turn: QueueTurn) -> SpeechStatus:
    """Raises AwaitingSpeechModelError with none chosen, and a failure Huey
    retries when the server stays down for two minutes. Gives the queue up
    while it waits, as a window does."""
    deadline = time.monotonic() + GIVE_UP_SECONDS
    while True:
        try:
            status = api.status()
        except UnavailableError:
            status = None
        if status is not None and status.ready:
            return status
        if status is not None and status.reason == "needs_speech_model":
            raise AwaitingSpeechModelError
        if time.monotonic() >= deadline:
            raise RecordingFailedError(ENGINE_STOPPED)
        turn.check_cancelled()
        turn.give_way()
        time.sleep(POLL_SECONDS)
