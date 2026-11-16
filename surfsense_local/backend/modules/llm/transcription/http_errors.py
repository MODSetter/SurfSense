"""How the transcription routes refuse: `{"detail": {"message", "code", ...}}`,
the app's convention, so the screen can say it in the interface language and
fall back to the English `message`."""

from fastapi import HTTPException, status

from modules.llm.transcription.gate import WaitReason
from modules.llm.transcription.memory_admission import TranscriptionNeedsMemoryError

__all__ = [
    "dictation_ended",
    "needs_memory",
    "needs_speech_model",
    "transcription_unavailable",
    "unfit_audio",
    "waiting",
]


def needs_speech_model() -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        {"message": "Choose a speech model first.", "code": "needs_speech_model"},
    )


def transcription_unavailable(reason: object) -> HTTPException:
    return HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        {
            "message": f"The speech recognition engine is not running: {reason}",
            "code": "transcription_unavailable",
        },
    )


def needs_memory(short: TranscriptionNeedsMemoryError) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, _memory_detail(short))


def dictation_ended() -> HTTPException:
    return HTTPException(
        status.HTTP_404_NOT_FOUND,
        {"message": "This dictation has ended.", "code": "dictation_ended"},
    )


def unfit_audio(problem: object) -> HTTPException:
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        {
            "message": f"The audio cannot be transcribed: {problem}",
            "code": "unfit_audio",
        },
    )


def waiting(
    reason: WaitReason | str, short: TranscriptionNeedsMemoryError | None = None
) -> HTTPException:
    """A file window not sent yet; the worker asks again."""
    detail = {"message": f"Waiting for the speech model: {reason}"}
    if short is not None:
        detail = _memory_detail(short)
    return HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        {**detail, "code": "waiting", "reason": reason},
    )


def _memory_detail(short: TranscriptionNeedsMemoryError) -> dict:
    return {
        "message": str(short),
        "code": "transcription_needs_memory",
        "needed_bytes": short.needed_bytes,
        "available_bytes": short.available_bytes,
    }
