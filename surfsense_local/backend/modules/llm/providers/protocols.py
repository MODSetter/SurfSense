from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol

from modules.llm.providers.types import Delta, Message, Model


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

    async def sees_images(self, model: str) -> bool | None:
        """Whether this model takes images, or None when it cannot be told.

        None is not no: a caller refusing images on it would hide them behind a
        hiccup, while the runtime still refuses what it cannot take.
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
        json_schema: dict | None = None,
        conversation: str | None = None,
    ) -> AsyncIterator[str]:
        """The answer text alone; a thinking model's trace is left out.

        `conversation` names the requests that share a prompt's start, so an
        endpoint that routes by it sends them to the cache that holds it.
        """
        ...

    def chat_deltas(
        self,
        model: str,
        messages: list[Message],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        reasoning: bool | None = None,
        json_schema: dict | None = None,
        conversation: str | None = None,
    ) -> AsyncIterator[Delta]:
        """The reply as it streams, with the trace marked apart from the answer."""
        ...


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
    # None where the source does not say: OpenAI documents none for its voices.
    gender: Literal["female", "male"] | None
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
    """Anything that voices a script: audio.cpp here, or a server's /audio/speech."""

    async def check_memory(self) -> None:
        """Raise, with the sentence a person reads, when voicing cannot fit."""
        ...

    async def synthesize(
        self, turns: list[SpokenTurn], language: str
    ) -> SynthesizedAudio: ...
