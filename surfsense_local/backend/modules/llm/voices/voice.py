"""One voice a model offers. Here, not under `providers/`, whose package loads the
chat provider, which needs `connections.service`, which needs this."""

from dataclasses import dataclass
from typing import Literal

__all__ = ["Voice"]


@dataclass(frozen=True)
class Voice:
    id: str
    label: str
    # None where the source does not say: OpenAI documents none for its voices.
    gender: Literal["female", "male"] | None
    # The languages this voice speaks, as the model's entry names them: one for
    # a Kokoro voice, every one the model speaks for a Supertonic voice.
    languages: tuple[str, ...]
