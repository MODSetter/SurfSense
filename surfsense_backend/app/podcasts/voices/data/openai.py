"""OpenAI TTS voices: language-agnostic, so each speaks any requested language.

OpenAI voices follow the language of the input text rather than being tied to a
locale, so they are tagged :data:`ANY_LANGUAGE` and match every brief. The
``native_ref`` is the plain voice name the API expects.
"""

from __future__ import annotations

from ..provider import TtsProvider
from ..voice import ANY_LANGUAGE, CatalogVoice, VoiceGender


def _voice(name: str, display: str, gender: VoiceGender) -> CatalogVoice:
    return CatalogVoice(
        voice_id=f"openai:{name}",
        provider=TtsProvider.OPENAI,
        language=ANY_LANGUAGE,
        display_name=display,
        gender=gender,
        native_ref=name,
    )


OPENAI_VOICES: tuple[CatalogVoice, ...] = (
    _voice("alloy", "Alloy", VoiceGender.NEUTRAL),
    _voice("echo", "Echo", VoiceGender.MALE),
    _voice("fable", "Fable", VoiceGender.NEUTRAL),
    _voice("onyx", "Onyx", VoiceGender.MALE),
    _voice("nova", "Nova", VoiceGender.FEMALE),
    _voice("shimmer", "Shimmer", VoiceGender.FEMALE),
)
