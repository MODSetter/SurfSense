"""Text-to-speech: a per-segment synthesis port with provider adapters.

Callers depend on :class:`TextToSpeech` and obtain the configured provider from
:func:`get_text_to_speech`; the concrete Kokoro/LiteLLM adapters stay private.
"""

from __future__ import annotations

from .audio import SynthesizedAudio
from .errors import TextToSpeechError
from .factory import get_text_to_speech
from .port import TextToSpeech
from .request import SynthesisRequest, VoiceRef

__all__ = [
    "SynthesisRequest",
    "SynthesizedAudio",
    "TextToSpeech",
    "TextToSpeechError",
    "VoiceRef",
    "get_text_to_speech",
]
