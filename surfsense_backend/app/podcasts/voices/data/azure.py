"""Azure TTS voices, routed through the OpenAI-compatible voice names.

The deployment fronts Azure with OpenAI-style voice names (matching the legacy
podcaster), so these mirror the OpenAI roster and, like it, speak any requested
language.
"""

from __future__ import annotations

from ..provider import TtsProvider
from ..voice import ANY_LANGUAGE, CatalogVoice, VoiceGender


def _voice(name: str, display: str, gender: VoiceGender) -> CatalogVoice:
    return CatalogVoice(
        voice_id=f"azure:{name}",
        provider=TtsProvider.AZURE,
        language=ANY_LANGUAGE,
        display_name=display,
        gender=gender,
        native_ref=name,
    )


AZURE_VOICES: tuple[CatalogVoice, ...] = (
    _voice("alloy", "Alloy", VoiceGender.NEUTRAL),
    _voice("echo", "Echo", VoiceGender.MALE),
    _voice("fable", "Fable", VoiceGender.NEUTRAL),
    _voice("onyx", "Onyx", VoiceGender.MALE),
    _voice("nova", "Nova", VoiceGender.FEMALE),
    _voice("shimmer", "Shimmer", VoiceGender.FEMALE),
)
