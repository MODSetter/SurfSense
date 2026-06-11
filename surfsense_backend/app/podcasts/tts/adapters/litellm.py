"""LiteLLM adapter: hosted TTS (OpenAI, Azure, Vertex AI) via one ``aspeech`` call.

LiteLLM normalises every hosted provider behind the same ``aspeech`` surface,
so a single adapter covers them all. The provider is encoded in the model
string (e.g. ``openai/tts-1``, ``vertex_ai/...``) and the voice reference is
whatever that provider expects, which the catalog already supplies.
"""

from __future__ import annotations

from ..audio import SynthesizedAudio
from ..errors import TextToSpeechError
from ..port import TextToSpeech
from ..request import SynthesisRequest

# Hosted providers return MP3-encoded bytes from ``aspeech``.
_CONTAINER = "mp3"

# A long single segment still finishes well under this; retries absorb transient
# upstream failures without failing the whole render.
_TIMEOUT_SECONDS = 600
_MAX_RETRIES = 2


class LiteLlmTextToSpeech(TextToSpeech):
    """Synthesises segments through any LiteLLM-supported hosted TTS model."""

    def __init__(
        self,
        *,
        model: str,
        api_base: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._model = model
        self._api_base = api_base
        self._api_key = api_key

    @property
    def container(self) -> str:
        return _CONTAINER

    async def synthesize(self, request: SynthesisRequest) -> SynthesizedAudio:
        from litellm import aspeech

        kwargs = {
            "model": self._model,
            "voice": request.voice,
            "input": request.text,
            "max_retries": _MAX_RETRIES,
            "timeout": _TIMEOUT_SECONDS,
        }
        if self._api_base:
            kwargs["api_base"] = self._api_base
        if self._api_key:
            kwargs["api_key"] = self._api_key

        try:
            response = await aspeech(**kwargs)
        except Exception as exc:
            raise TextToSpeechError(f"{self._model} synthesis failed: {exc}") from exc

        data = getattr(response, "content", None)
        if not data:
            raise TextToSpeechError(f"{self._model} returned no audio")

        return SynthesizedAudio(data=data, container=_CONTAINER)
