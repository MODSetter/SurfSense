"""What the renderer hands a TTS provider to voice a single segment."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

# A provider-native voice reference. OpenAI/Azure/Kokoro name a voice with a
# string; Vertex passes a mapping (``languageCode`` + ``name``). The catalog
# stores whichever shape the provider expects and we pass it through untouched.
VoiceRef = str | Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class SynthesisRequest:
    """One unit of speech to synthesise: the smallest cacheable render step."""

    text: str
    voice: VoiceRef
    language: str
    speed: float = 1.0
