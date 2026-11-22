"""The language the user says they speak, kept under `transcription` in the
speech_to_text selection's settings. Only this module reads or writes it.

Never rewritten from a detection, and dropped with the rest of the settings
when the slot takes another model.
"""

from sqlalchemy.orm import Session

from modules.llm.catalog.local.engines.audiocpp.manifest_fields import (
    TranscriptionDefaults,
)
from modules.llm.models import SelectedModel

__all__ = ["AUTO", "keep_language_intent", "language_intent"]

KEY = "transcription"
# Let the model detect the language, phrase by phrase and window by window.
AUTO = "auto"


def language_intent(
    selected: SelectedModel, transcription: TranscriptionDefaults
) -> str:
    """The kept language, or else `auto`; a model that cannot detect gets its
    first language instead, since told nothing it translates into English."""
    kept = ((selected.settings or {}).get(KEY) or {}).get("language")
    if kept in transcription.languages:
        return kept
    return AUTO if transcription.detects_language else transcription.languages[0]


def keep_language_intent(
    session: Session, selected: SelectedModel, language: str
) -> None:
    """`language` is `auto` or one the caller checked the model lists."""
    # Reassigned, not mutated: a JSON column tracks assignment only.
    settings = {
        key: value for key, value in (selected.settings or {}).items() if key != KEY
    }
    settings[KEY] = {"language": language}
    selected.settings = settings
    session.flush()
