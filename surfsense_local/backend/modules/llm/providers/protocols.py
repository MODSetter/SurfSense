from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

from modules.llm.providers.types import Message, Model


class Generator(Protocol):
    """Anything that can answer. llama.cpp locally, or a remote endpoint."""

    name: str

    async def health(self) -> bool: ...

    async def models(self) -> list[Model]: ...

    async def context_tokens(self, model: str) -> int | None:
        """The window this model was loaded with, or None when it is not known.

        None is a fact, not a zero: a remote endpoint this app does not run
        rarely states its window at all, and callers that budget a prompt from
        this must treat that as "unknown" rather than "narrow".
        """
        ...

    async def token_count(self, model: str, text: str) -> int | None:
        """This text's exact cost by the model's own tokenizer, or None.

        None on anything short of a clean count: no such endpoint, a transient
        failure, or a model this generator does not run. A caller pricing a
        prompt from this must fall back to an estimate rather than treat None
        as zero tokens.
        """
        ...

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
    # The languages this voice speaks, as the model's entry names them: one for
    # a Kokoro voice, every one the model speaks for a Supertonic voice.
    languages: tuple[str, ...]


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
    """Anything that voices a script: audio.cpp on this computer today."""

    def voices(self) -> list[Voice]: ...

    def check_memory(self) -> None:
        """Raise, with the sentence a person reads, when voicing cannot fit."""
        ...

    async def synthesize(
        self, turns: list[SpokenTurn], language: str
    ) -> SynthesizedAudio: ...
