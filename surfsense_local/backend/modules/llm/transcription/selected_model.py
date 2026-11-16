"""The chosen speech model as a request needs it: the id the server knows it
by, its reviewed languages and memory, and the language the user set."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from modules.llm.catalog.local.engines.audiocpp.manifest_fields import (
    TranscriptionDefaults,
)
from modules.llm.resolution import resolve_speech_to_text
from modules.llm.transcription.language_intent import language_intent

__all__ = ["SpeechModel", "selected_speech_model"]


@dataclass(frozen=True)
class SpeechModel:
    model_id: str
    transcription: TranscriptionDefaults
    # `auto`, or a language the model is listed for.
    language_intent: str


def selected_speech_model(session: Session) -> SpeechModel:
    """Raises NoSpeechModelError without one."""
    chosen = resolve_speech_to_text(session)
    transcription = chosen.recogniser.transcription
    return SpeechModel(
        chosen.recogniser.model_id,
        transcription,
        language_intent(chosen.selection, transcription),
    )
