"""A catalog voice: a stable id paired with its provider-native reference."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.podcasts.tts import VoiceRef

from .provider import TtsProvider

# A voice that speaks whatever language the input text is in (e.g. OpenAI's
# voices), matched against every requested language.
ANY_LANGUAGE = "*"


class VoiceGender(StrEnum):
    """Perceived voice gender, used to pick distinct voices per speaker."""

    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"


@dataclass(frozen=True, slots=True)
class CatalogVoice:
    """One selectable voice.

    ``voice_id`` is the provider-prefixed, stable id stored on a speaker in the
    brief (e.g. ``"kokoro:am_adam"``). ``native_ref`` is the untyped value the
    TTS adapter passes to the provider — a string for most, a mapping for
    Vertex — kept separate so renaming the catalog id never breaks synthesis.
    """

    voice_id: str
    provider: TtsProvider
    language: str
    display_name: str
    gender: VoiceGender
    native_ref: VoiceRef

    def speaks(self, language: str) -> bool:
        """Whether this voice can render ``language`` (primary subtag match)."""
        if self.language == ANY_LANGUAGE:
            return True
        return _primary(self.language) == _primary(language)


def _primary(language: str) -> str:
    return language.split("-", 1)[0].strip().lower()
