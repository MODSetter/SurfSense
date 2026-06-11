"""The TTS providers we carry voices for, and how to name one from config."""

from __future__ import annotations

from enum import StrEnum


class TtsProvider(StrEnum):
    """A speech provider whose voices the catalog enumerates."""

    KOKORO = "kokoro"
    OPENAI = "openai"
    AZURE = "azure"
    VERTEX_AI = "vertex_ai"


def provider_from_service(service: str) -> TtsProvider:
    """Map a ``TTS_SERVICE`` string to its provider.

    The config value is a LiteLLM-style ``provider/model`` string
    (``openai/tts-1``, ``vertex_ai/...``) except for local Kokoro, which is
    spelled ``local/kokoro``; both halves of that special case resolve here.
    """
    prefix = service.split("/", 1)[0].strip().lower()
    if prefix == "local":
        return TtsProvider.KOKORO
    return TtsProvider(prefix)
