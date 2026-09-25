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
class Message:
    """One turn of a conversation handed to a generator."""

    role: str
    content: str


@dataclass(frozen=True)
class Delta:
    """One streamed piece of a reply: answer text, or the model's reasoning."""

    text: str
    reasoning: bool = False


@dataclass(frozen=True)
class DownloadProgress:
    """How far a model download has come, as the runtime reports it."""

    status: str
    completed: int = 0
    total: int = 0
