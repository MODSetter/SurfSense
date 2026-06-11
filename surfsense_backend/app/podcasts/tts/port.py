"""The TTS contract: turn one segment of text into encoded audio."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .audio import SynthesizedAudio
from .request import SynthesisRequest


class TextToSpeech(ABC):
    """Synthesises a single segment; one implementation per provider.

    The contract is intentionally per-segment rather than per-episode: it keeps
    each call independently cacheable and lets the renderer cap concurrency and
    retry segments in isolation. Stitching segments into one file is the
    renderer's job, not the provider's.
    """

    @property
    @abstractmethod
    def container(self) -> str:
        """File extension/container this provider emits (e.g. ``"mp3"``)."""

    @abstractmethod
    async def synthesize(self, request: SynthesisRequest) -> SynthesizedAudio:
        """Voice ``request.text`` and return its encoded audio.

        Raises :class:`~app.podcasts.tts.errors.TextToSpeechError` on any
        provider or configuration failure.
        """
