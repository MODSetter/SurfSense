"""Audible previews so users pick voices by sound, not by name.

A preview is a short sample sentence synthesised in the voice's own language.
Samples are served through the same content-addressed cache the renderer uses,
so each voice costs at most one synthesis per cache lifetime — repeat listens
while comparing voices are free.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from app.podcasts.rendering.cache import SegmentCache
from app.podcasts.tts import SynthesisRequest, TextToSpeech

from .voice import ANY_LANGUAGE, CatalogVoice

# Previews are user-independent, so one rendered sample serves everyone.
PREVIEW_CACHE_ROOT = Path(tempfile.gettempdir()) / "surfsense_podcasts" / "previews"

_FALLBACK_LANGUAGE = "en"

# A voice previews best speaking its own language.
_SAMPLE_TEXTS = {
    "en": "Hi there! This is how I sound when narrating your podcast.",
    "es": "¡Hola! Así sueno cuando narro tu pódcast.",
    "fr": "Bonjour ! Voici ma voix quand je raconte votre podcast.",
    "hi": "नमस्ते! आपका पॉडकास्ट सुनाते समय मेरी आवाज़ ऐसी होती है।",
    "it": "Ciao! Questa è la mia voce quando racconto il tuo podcast.",
    "ja": "こんにちは。ポッドキャストをお届けするときの私の声です。",
    "pt": "Olá! É assim que eu soo ao narrar o seu podcast.",
    "zh": "你好！这就是我为你播报播客时的声音。",
}

_CONTENT_TYPES = {"mp3": "audio/mpeg", "wav": "audio/wav"}


async def render_voice_preview(
    voice: CatalogVoice, tts: TextToSpeech
) -> tuple[bytes, str]:
    """Return ``(audio_bytes, content_type)`` for a sample spoken by ``voice``."""
    language = (
        _FALLBACK_LANGUAGE if voice.language == ANY_LANGUAGE else voice.language
    )
    request = SynthesisRequest(
        text=_sample_text(language), voice=voice.native_ref, language=language
    )

    cache = SegmentCache(PREVIEW_CACHE_ROOT)
    key = cache.key(request)
    cached = cache.get(key, tts.container)
    if cached is not None:
        return cached.read_bytes(), _content_type(tts.container)

    audio = await tts.synthesize(request)
    cache.put(key, audio.container, audio.data)
    return audio.data, _content_type(audio.container)


def _sample_text(language: str) -> str:
    primary = language.split("-", 1)[0].strip().lower()
    return _SAMPLE_TEXTS.get(primary, _SAMPLE_TEXTS[_FALLBACK_LANGUAGE])


def _content_type(container: str) -> str:
    return _CONTENT_TYPES.get(container, "application/octet-stream")
