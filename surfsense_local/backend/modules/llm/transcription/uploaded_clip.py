"""A phrase or window from a multipart upload, read no further than 30 s of
audio could be, and checked before anything else happens."""

from fastapi import UploadFile

from modules.llm.transcription import http_errors
from modules.llm.transcription.audio_checks import (
    MAX_WAV_BYTES,
    CheckedAudio,
    UnfitAudioError,
    checked_audio,
)

__all__ = ["uploaded_clip"]


async def uploaded_clip(audio: UploadFile) -> CheckedAudio:
    data = await audio.read(MAX_WAV_BYTES + 1)
    if len(data) > MAX_WAV_BYTES:
        raise http_errors.unfit_audio("longer than 30 s")
    try:
        return checked_audio(data)
    except UnfitAudioError as problem:
        raise http_errors.unfit_audio(problem) from problem
