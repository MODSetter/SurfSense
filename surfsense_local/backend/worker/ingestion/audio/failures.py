"""Why a recording failed, in the sentence its row shows as written."""

__all__ = [
    "ENGINE_STOPPED",
    "NO_AUDIO",
    "NO_SPEECH",
    "UNDECODABLE",
    "AwaitingSpeechModelError",
    "RecordingFailedError",
    "RecordingRefusedError",
    "no_room",
]

NO_SPEECH = "No speech was found in this recording."
NO_AUDIO = "This file has no audio."
UNDECODABLE = "This recording could not be decoded."
ENGINE_STOPPED = "The speech recognition engine stopped."


class RecordingFailedError(Exception):
    """The message is a sentence for the person; Huey tries again."""


class RecordingRefusedError(RecordingFailedError):
    """The same recording would fail the same way again: no retry."""


class AwaitingSpeechModelError(RecordingRefusedError):
    """No speech model is chosen: choosing one queues the recording again."""

    def __init__(self) -> None:
        super().__init__("Waiting for a speech model.")


def no_room(needed_bytes: int) -> RecordingRefusedError:
    return RecordingRefusedError(
        f"Transcribing needs about {needed_bytes / 1e9:.1f} GB of free disk space."
    )
