"""Resolve the configured :class:`TextToSpeech` as a process-wide singleton."""

from __future__ import annotations

from functools import lru_cache

from .port import TextToSpeech

# Sentinel model string that selects the local Kokoro pipeline; anything else is
# treated as a LiteLLM-hosted model (``openai/...``, ``vertex_ai/...``, etc.).
KOKORO_SERVICE = "local/kokoro"


@lru_cache(maxsize=1)
def get_text_to_speech() -> TextToSpeech:
    """Build the provider selected by ``TTS_SERVICE`` (adapters lazy-imported).

    Cached because the Kokoro adapter holds loaded pipelines that must be reused
    across segments and requests rather than rebuilt per call.
    """
    from app.config import config as app_config

    service = app_config.TTS_SERVICE
    if not service:
        raise ValueError("TTS_SERVICE is not configured")

    if service == KOKORO_SERVICE:
        from .adapters.kokoro import KokoroTextToSpeech

        return KokoroTextToSpeech()

    from .adapters.litellm import LiteLlmTextToSpeech

    return LiteLlmTextToSpeech(
        model=service,
        api_base=app_config.TTS_SERVICE_API_BASE,
        api_key=app_config.TTS_SERVICE_API_KEY,
    )
