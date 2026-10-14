"""Dictation in the composer: whether it can run, a session per mic press, and
one request per phrase. Phrases are held in memory only, here as on screen."""

from typing import Annotated, Literal

from fastapi import APIRouter, File, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool
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
from modules.llm.transcription.language_intent import AUTO
from modules.llm.transcription.memory_admission import (
    TranscriptionNeedsMemoryError,
    admit_transcription,
)
from modules.llm.transcription.recognition import recognise
from modules.llm.transcription.selected_model import (
    SpeechModel,
    selected_speech_model,
)
from modules.llm.transcription.server import transcriber_here
from modules.llm.transcription.sessions import DictationEndedError, DictationSessions
from modules.llm.transcription.uploaded_clip import uploaded_clip
from modules.llm.transcription.voice_activity.speech_spans import speech_spans
from modules.llm.transcription.warm_up import warm_in_background

router = APIRouter(prefix="/transcription", tags=["llm"])


class StatusRead(BaseModel):
    ready: bool
    reason: Literal["needs_speech_model", "transcription_unavailable"] | None
    model: str | None
    # `auto`, or one of `languages`.
    language_intent: str
    languages: list[str]


class DictationRead(BaseModel):
    id: str
    # `loading`: the first phrase waits for the model to load.
    warm: Literal["loaded", "loading"]


class PhraseRead(BaseModel):
    text: str
    language: str | None
    # Silero heard under 250 ms of speech, so the model was not asked.
    no_speech: bool


AudioPart = Annotated[
    UploadFile, File(description="16 kHz mono 16-bit WAV, at most 30 s")
]


@router.get("/status", response_model=StatusRead)
async def read_status(session: SessionDep) -> StatusRead:
    try:
        model = await transact(session, selected_speech_model)
    except NoSpeechModelError:
        return StatusRead(
            ready=False,
            reason="needs_speech_model",
            model=None,
            language_intent=AUTO,
            languages=[],
        )
    reason: Literal["transcription_unavailable"] | None = None
    transcriber = transcriber_here()
    try:
        if transcriber is None:
            raise TranscriptionUnavailableError("this build has no audio.cpp")
        await transcriber.is_loaded(model.model_id)
    except TranscriptionUnavailableError:
        reason = "transcription_unavailable"
    return StatusRead(
        ready=reason is None,
        reason=reason,
        model=model.model_id,
        language_intent=model.language_intent,
        languages=list(model.transcription.languages),
    )


@router.post(
    "/dictations", status_code=status.HTTP_201_CREATED, response_model=DictationRead
)
async def open_dictation(
    session: SessionDep,
    gate: GateDep,
    dictations: DictationsDep,
    transcriber: TranscriberDep,
) -> DictationRead:
    """Refused before the speaker says anything when memory is short; any
    other open dictation ends."""
    model = await _speech_model(session)
    try:
        loaded = await admit_transcription(
            transcriber, model.model_id, model.transcription.peak_mb
        )
    except TranscriptionNeedsMemoryError as short:
        raise http_errors.needs_memory(short) from short
    except TranscriptionUnavailableError as error:
        raise http_errors.transcription_unavailable(error) from error
    dictation = dictations.open()
    if not loaded:
        warm_in_background(gate, transcriber, model.model_id)
    return DictationRead(id=dictation, warm="loaded" if loaded else "loading")


@router.post("/dictations/{dictation_id}/phrases", response_model=PhraseRead)
async def transcribe_phrase(
    dictation_id: str,
    audio: AudioPart,
    session: SessionDep,
    gate: GateDep,
    dictations: DictationsDep,
    transcriber: TranscriberDep,
) -> PhraseRead:
    _keep_open(dictations, dictation_id)
    clip = await uploaded_clip(audio)
    # Off the event loop: a 20 s phrase is some 600 runs of the model.
    if await run_in_threadpool(speech_spans, clip.pcm) == []:
        return PhraseRead(text="", language=None, no_speech=True)
    try:
        model = await transact(session, selected_speech_model)
    except NoSpeechModelError as error:
        # Deleted since the mic was pressed: this dictation cannot go on.
        dictations.close(dictation_id)
        raise http_errors.needs_speech_model() from error
    try:
        async with gate.dictation_turn(model.model_id):
            await admit_transcription(
                transcriber, model.model_id, model.transcription.peak_mb
            )
            recognised = await recognise(transcriber, model, clip)
    except TranscriptionNeedsMemoryError as short:
        raise http_errors.needs_memory(short) from short
    except TranscriptionUnavailableError as error:
        raise http_errors.transcription_unavailable(error) from error
    except ModelBusyError as error:
        # Being deleted: as above.
        dictations.close(dictation_id)
        raise http_errors.needs_speech_model() from error
    return PhraseRead(
        text=recognised.text, language=recognised.language, no_speech=False
    )


@router.post(
    "/dictations/{dictation_id}/keepalive", status_code=status.HTTP_204_NO_CONTENT
)
def keep_dictation_open(dictation_id: str, dictations: DictationsDep) -> Response:
    """Every 10 s while recording, so a long pause does not end it."""
    _keep_open(dictations, dictation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/dictations/{dictation_id}", status_code=status.HTTP_204_NO_CONTENT)
def close_dictation(dictation_id: str, dictations: DictationsDep) -> Response:
    """After the last phrase: recordings may use the server again."""
    dictations.close(dictation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _speech_model(session: SessionDep) -> SpeechModel:
    try:
        return await transact(session, selected_speech_model)
    except NoSpeechModelError as error:
        raise http_errors.needs_speech_model() from error


def _keep_open(dictations: DictationSessions, dictation_id: str) -> None:
    try:
        dictations.touch(dictation_id)
    except DictationEndedError as error:
        raise http_errors.dictation_ended() from error
