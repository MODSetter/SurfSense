"""Vertex AI Studio voices: locale-specific, referenced by a mapping.

Vertex voices are tied to a locale and named via a ``{languageCode, name}``
mapping, which is exactly the ``native_ref`` the LiteLLM adapter forwards. The
values mirror the legacy podcaster's English Studio voices.
"""

from __future__ import annotations

from ..provider import TtsProvider
from ..voice import CatalogVoice, VoiceGender


def _voice(
    key: str,
    language: str,
    locale: str,
    name: str,
    display: str,
    gender: VoiceGender,
) -> CatalogVoice:
    return CatalogVoice(
        voice_id=f"vertex_ai:{key}",
        provider=TtsProvider.VERTEX_AI,
        language=language,
        display_name=display,
        gender=gender,
        native_ref={"languageCode": locale, "name": name},
    )


VERTEX_VOICES: tuple[CatalogVoice, ...] = (
    _voice("en-US-Studio-O", "en-US", "en-US", "en-US-Studio-O", "Studio O (US)", VoiceGender.FEMALE),
    _voice("en-US-Studio-M", "en-US", "en-US", "en-US-Studio-M", "Studio M (US)", VoiceGender.MALE),
    _voice("en-GB-Studio-A", "en-GB", "en-UK", "en-UK-Studio-A", "Studio A (UK)", VoiceGender.FEMALE),
    _voice("en-GB-Studio-B", "en-GB", "en-UK", "en-UK-Studio-B", "Studio B (UK)", VoiceGender.MALE),
    _voice("en-AU-Studio-A", "en-AU", "en-AU", "en-AU-Studio-A", "Studio A (AU)", VoiceGender.FEMALE),
    _voice("en-AU-Studio-B", "en-AU", "en-AU", "en-AU-Studio-B", "Studio B (AU)", VoiceGender.MALE),
)
