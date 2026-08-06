"""Pick the language and voice a presentation should be narrated in.

The video agent shares the podcast voice catalog rather than carrying its own
provider-to-voice map, so a Japanese deck is narrated by a Japanese voice
instead of an American English one reading Japanese text. The language the
model declares on its slide output is the primary signal; a missing or
malformed one degrades to the operator default and finally to English, and a
language the configured provider cannot actually speak degrades the same way.
Narration must never fail because of a bad tag.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.podcasts.resolution import DEFAULT_LANGUAGE, resolve_voices
from app.podcasts.schemas import normalize_language_tag
from app.podcasts.tts import VoiceRef
from app.podcasts.voices import (
    TtsProvider,
    VoiceCatalog,
    get_voice_catalog,
    provider_from_service,
)

# The voice each provider narrated with before narration became language-aware.
# Seeded as the preferred choice so an English deck keeps exactly the voice it
# had: the catalog lists am_adam before af_heart, so dropping the seed would
# silently re-cast every existing English presentation. For any other language
# the seed does not fit and is discarded, letting the catalog pick a native one.
_LEGACY_ENGLISH_VOICE_ID: dict[TtsProvider, str] = {
    TtsProvider.KOKORO: "kokoro:af_heart",
    TtsProvider.OPENAI: "openai:alloy",
    TtsProvider.AZURE: "azure:alloy",
    TtsProvider.VERTEX_AI: "vertex_ai:en-US-Studio-O",
}


@dataclass(frozen=True, slots=True)
class NarrationVoice:
    """The language tag and provider-native voice reference to synthesise with."""

    language: str
    voice: VoiceRef


def resolve_narration(declared: str | None) -> NarrationVoice:
    """Decide how to narrate a deck the model says it wrote in ``declared``."""
    provider = _active_provider()
    catalog = get_voice_catalog()
    language = _supported_language(declared, provider=provider, catalog=catalog)
    voice = _default_voice(language=language, provider=provider, catalog=catalog)
    return NarrationVoice(language=language, voice=voice)


def _active_provider() -> TtsProvider:
    from app.config import config as app_config

    service = app_config.TTS_SERVICE
    if not service:
        raise ValueError("TTS_SERVICE is not configured")
    return provider_from_service(service)


def _supported_language(
    declared: str | None, *, provider: TtsProvider, catalog: VoiceCatalog
) -> str:
    """Return the first candidate the provider can actually speak.

    Mirrors the podcast brief's resolve-normalise-verify funnel so the two
    features agree on what a usable language is.
    """
    from app.config import config as app_config

    candidates = (declared, app_config.VIDEO_PRESENTATION_DEFAULT_LANGUAGE)
    for candidate in candidates:
        if not candidate or not candidate.strip():
            continue
        try:
            language = normalize_language_tag(candidate)
        except ValueError:
            continue
        if catalog.supports_language(provider, language):
            return language
    return DEFAULT_LANGUAGE


def _default_voice(
    *, language: str, provider: TtsProvider, catalog: VoiceCatalog
) -> VoiceRef:
    seed = _LEGACY_ENGLISH_VOICE_ID.get(provider)
    voices = resolve_voices(
        catalog=catalog,
        provider=provider,
        language=language,
        speaker_count=1,
        preferred=[seed] if seed else None,
    )
    return voices[0].native_ref
