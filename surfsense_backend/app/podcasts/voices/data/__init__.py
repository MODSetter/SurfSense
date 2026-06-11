"""Static per-provider voice rosters that compose the catalog."""

from __future__ import annotations

from .azure import AZURE_VOICES
from .kokoro import KOKORO_VOICES
from .openai import OPENAI_VOICES
from .vertex import VERTEX_VOICES

__all__ = ["AZURE_VOICES", "KOKORO_VOICES", "OPENAI_VOICES", "VERTEX_VOICES"]
