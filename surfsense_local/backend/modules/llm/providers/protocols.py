from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

from modules.llm.providers.types import Message, Model


class Generator(Protocol):
    """Anything that can answer. llama.cpp locally, or a remote endpoint."""

    name: str

    async def health(self) -> bool: ...

    async def models(self) -> list[Model]: ...

    def chat(
        self,
        model: str,
        messages: list[Message],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        reasoning: bool | None = None,
    ) -> AsyncIterator[str]: ...


@dataclass(frozen=True)
class GeneratedImage:
    content: bytes
    media_type: str


class ImageGenerator(Protocol):
    async def generate(self, model: str, prompt: str) -> GeneratedImage: ...


@dataclass(frozen=True)
class Voice:
    id: str
    label: str
    language: str  # BCP-47, e.g. "en-US", "pt-BR"


@dataclass(frozen=True)
class SpokenTurn:
    """One spoken line: which voice says it, and what."""

    voice: str
    text: str


@dataclass(frozen=True)
class SynthesizedAudio:
    content: bytes
    media_type: str


class TextToSpeech(Protocol):
    """Anything that voices a script. Kokoro on this CPU today, hosted APIs later."""

    def voices(self) -> list[Voice]: ...

    async def synthesize(self, turns: list[SpokenTurn]) -> SynthesizedAudio: ...
