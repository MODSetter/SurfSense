"""The deterministic builder strategy: prompt the model, render its answer."""

from collections.abc import Callable
from dataclasses import dataclass

from worker.studio.artifact import Built, Source


@dataclass(frozen=True)
class Builder:
    """A format: how to prompt the model, and how to render its answer.

    A new format is one module and one line in the registry — persistence and
    the routes stay format-blind.
    """

    key: str
    prompt: Callable[[list[Source], str | None], str]
    build: Callable[[str, list[Source]], Built]
