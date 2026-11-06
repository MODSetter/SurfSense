"""The model a job's runner asks, and what one call gives back: every runner, and the eval harness's
models, speak this one protocol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ModelReply:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class AnswerModel(Protocol):
    """The model a job runs on; the app's selected model in Studio, a fixed one in an eval.

    `shared` is how many leading characters of the first turn every question repeats:
    a provider that caches by marked blocks marks that much.
    """

    name: str
    window: int | None  # tokens it reads at once; None when it is not known
    concurrency: int  # questions it may take at once

    def ask(
        self, system: str, turns: list[tuple[str, str]], schema: dict, shared: int
    ) -> ModelReply: ...
