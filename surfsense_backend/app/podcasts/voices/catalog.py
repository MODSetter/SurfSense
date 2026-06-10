"""The voice catalog: look up and filter selectable voices.

A :class:`VoiceCatalog` is the single source of truth for which voices exist,
replacing the hardcoded speaker-id maps. Resolution uses it to pick defaults
for a brief, the API exposes it as picker options, and the renderer uses it to
turn a stored ``voice_id`` back into the provider-native reference.
"""

from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache

from .data import AZURE_VOICES, KOKORO_VOICES, OPENAI_VOICES, VERTEX_VOICES
from .provider import TtsProvider
from .voice import CatalogVoice


class VoiceCatalog:
    """An indexed, read-only collection of :class:`CatalogVoice`."""

    def __init__(self, voices: Iterable[CatalogVoice]) -> None:
        self._by_id: dict[str, CatalogVoice] = {}
        self._by_provider: dict[TtsProvider, list[CatalogVoice]] = {}
        for voice in voices:
            if voice.voice_id in self._by_id:
                raise ValueError(f"duplicate voice_id: {voice.voice_id}")
            self._by_id[voice.voice_id] = voice
            self._by_provider.setdefault(voice.provider, []).append(voice)

    def get(self, voice_id: str) -> CatalogVoice:
        """Return the voice with ``voice_id`` or raise ``KeyError``."""
        return self._by_id[voice_id]

    def for_provider(self, provider: TtsProvider) -> list[CatalogVoice]:
        """All voices offered by ``provider``, in catalog order."""
        return list(self._by_provider.get(provider, ()))

    def for_language(
        self, provider: TtsProvider, language: str
    ) -> list[CatalogVoice]:
        """``provider`` voices that can render ``language``, in catalog order."""
        return [v for v in self.for_provider(provider) if v.speaks(language)]

    def supports_language(self, provider: TtsProvider, language: str) -> bool:
        """Whether ``provider`` has at least one voice for ``language``."""
        return any(v.speaks(language) for v in self.for_provider(provider))


@lru_cache(maxsize=1)
def get_voice_catalog() -> VoiceCatalog:
    """The process-wide catalog assembled from every provider's roster."""
    return VoiceCatalog(
        (*KOKORO_VOICES, *OPENAI_VOICES, *AZURE_VOICES, *VERTEX_VOICES)
    )
