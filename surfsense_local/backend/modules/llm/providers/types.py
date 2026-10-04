from dataclasses import dataclass

from modules.llm.model_type import ModelType


@dataclass(frozen=True)
class Model:
    """A model a provider can answer with, once it is installed."""

    name: str
    installed: bool
    capabilities: tuple[str, ...] = ()
    display_name: str | None = None
    # What the model is for. `known` is False where nothing could say, and an
    # unknown model fills every slot: the user can see it answer first.
    types: tuple[ModelType, ...] = ()
    known: bool = True


@dataclass(frozen=True)
class Image:
    """An image a turn carries, already in a format every endpoint decodes."""

    mime: str
    data: bytes


@dataclass(frozen=True)
class Message:
    """One turn of a conversation handed to a generator."""

    role: str
    content: str
    # Beside the text, not inside it, so every reader of `content` stays a str.
    images: tuple[Image, ...] = ()


@dataclass(frozen=True)
class PromptProgress:
    """How much of the prompt the model has read, in tokens it had left to read."""

    processed: int
    total: int


@dataclass(frozen=True)
class Delta:
    """One streamed piece of a reply: answer text, the model's reasoning, or,
    with no text, how far it has read the prompt."""

    text: str
    reasoning: bool = False
    progress: PromptProgress | None = None


@dataclass(frozen=True)
class DownloadProgress:
    """How far a model download has come, as the runtime reports it."""

    status: str
    completed: int = 0
    total: int = 0
