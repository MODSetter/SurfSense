"""Voices: the catalog of selectable TTS voices and the active provider.

Callers obtain the catalog via :func:`get_voice_catalog` and identify the
configured provider via :func:`provider_from_service`.
"""

from __future__ import annotations

from .catalog import VoiceCatalog, get_voice_catalog
from .provider import TtsProvider, provider_from_service
from .voice import ANY_LANGUAGE, CatalogVoice, VoiceGender

__all__ = [
    "ANY_LANGUAGE",
    "CatalogVoice",
    "TtsProvider",
    "VoiceCatalog",
    "VoiceGender",
    "get_voice_catalog",
    "provider_from_service",
]
