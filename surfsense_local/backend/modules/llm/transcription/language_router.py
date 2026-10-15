"""Which language the chosen speech model listens for: Settings' select."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, StringConstraints
from sqlalchemy.orm import Session

from api.dependencies import SessionDep
from modules.llm.resolution import (
    NoSpeechModelError,
    ResolvedSpeechToText,
    resolve_speech_to_text,
)
from modules.llm.transcription import http_errors
from modules.llm.transcription.language_intent import (
    AUTO,
    keep_language_intent,
    language_intent,
)

router = APIRouter(prefix="/selection/speech_to_text/language", tags=["llm"])

Language = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=16)
]


class LanguageRead(BaseModel):
    # `auto`, or one of `languages`.
    language: str
    # ISO 639-1 codes the model is listed for, best first.
    languages: list[str]
    # Whether `auto` detects, rather than falling back to the model's default.
    detects_language: bool


class LanguageWrite(BaseModel):
    language: Language


@router.get("", response_model=LanguageRead)
def read_language(session: SessionDep) -> LanguageRead:
    return _read(_speech_model(session))


@router.put("", response_model=LanguageRead)
def set_language(payload: LanguageWrite, session: SessionDep) -> LanguageRead:
    chosen = _speech_model(session)
    transcription = chosen.recogniser.transcription
    offered = [*transcription.languages]
    if transcription.detects_language:
        offered.append(AUTO)
    if payload.language not in offered:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {
                "message": f"The speech model is not listed for {payload.language}.",
                "code": "language_not_listed",
            },
        )
    keep_language_intent(session, chosen.selection, payload.language)
    session.commit()
    return _read(chosen)


def _speech_model(session: Session) -> ResolvedSpeechToText:
    try:
        return resolve_speech_to_text(session)
    except NoSpeechModelError as error:
        raise http_errors.needs_speech_model() from error


def _read(chosen: ResolvedSpeechToText) -> LanguageRead:
    transcription = chosen.recogniser.transcription
    return LanguageRead(
        language=language_intent(chosen.selection, transcription),
        languages=list(transcription.languages),
        detects_language=transcription.detects_language,
    )
