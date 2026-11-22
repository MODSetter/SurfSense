"""A recording's windows from the ingest worker, which reaches speech
recognition only through the API, so one gate orders every request."""

import asyncio
import time
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel

from api.dependencies import SessionDep, transact
from modules.llm.activity import ModelBusyError
from modules.llm.providers.protocols import TranscriptionUnavailableError
from modules.llm.resolution import NoSpeechModelError
from modules.llm.transcription import http_errors
from modules.llm.transcription.dependencies import (
    DictationsDep,
    GateDep,
    TranscriberDep,
)
from modules.llm.transcription.gate import WindowWaitError
from modules.llm.transcription.memory_admission import (
    TranscriptionNeedsMemoryError,
    admit_transcription,
)
from modules.llm.transcription.recognition import recognise
from modules.llm.transcription.selected_model import selected_speech_model
from modules.llm.transcription.uploaded_clip import uploaded_clip

router = APIRouter(prefix="/internal/transcription", tags=["llm"])

# Then `503 waiting`: the worker checks for cancel and its turn to yield, and
# asks again.
WAIT_SECONDS = 30.0
# Memory comes back as other work ends; the job counts these waits.
MEMORY_POLL_SECONDS = 5.0


class WindowRead(BaseModel):
    text: str
    # A language code, or None when nothing says which.
    language: str | None
    # So the job resumes only windows transcribed by the same model.
    model_id: str


@router.post(
    "/windows",
    response_model=WindowRead,
    summary="Transcribe a recording's window for the ingest worker (loopback only)",
)
async def transcribe_window(
    audio: Annotated[
        UploadFile, File(description="16 kHz mono 16-bit WAV, at most 30 s")
    ],
    session: SessionDep,
    gate: GateDep,
    dictations: DictationsDep,
    transcriber: TranscriberDep,
    # No other recording is pending: the model goes once this one is done.
    last: Annotated[bool, Form()] = False,
) -> WindowRead:
    """`503 waiting` with a `reason` (dictation, hold, memory, busy) after at
    most 30 s; memory also carries both sizes."""
    clip = await uploaded_clip(audio)
    try:
        model = await transact(session, selected_speech_model)
    except NoSpeechModelError as error:
        raise http_errors.needs_speech_model() from error
    deadline = time.monotonic() + WAIT_SECONDS
    while True:
        short: TranscriptionNeedsMemoryError | None = None
        try:
            async with gate.window_turn(
                model.model_id, wait_seconds=deadline - time.monotonic()
            ):
                try:
                    await admit_transcription(
                        transcriber, model.model_id, model.transcription.peak_mb
                    )
                except TranscriptionNeedsMemoryError as error:
                    short = error
                else:
                    recognised = await recognise(transcriber, model, clip)
                    # As a podcast does when it ends, unless the speaker needs it.
                    if last and not dictations.any_open():
                        await transcriber.unload(model.model_id)
                    return WindowRead(
                        text=recognised.text,
                        language=recognised.language,
                        model_id=model.model_id,
                    )
        except WindowWaitError as waiting:
            raise http_errors.waiting(waiting.reason) from waiting
        except TranscriptionUnavailableError as error:
            raise http_errors.transcription_unavailable(error) from error
        except ModelBusyError as error:
            raise http_errors.needs_speech_model() from error
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise http_errors.waiting("memory", short)
        # Off the gate while it waits, so a phrase is never held up by it.
        await asyncio.sleep(min(MEMORY_POLL_SECONDS, remaining))
