"""Arm protocol + the value types every arm exchanges with a runner.

An ``Arm`` is "one way to answer one question". Two ship in this PR:

* ``NativePdfArm`` — drop the PDF straight into an OpenRouter
  chat-completions request with ``plugins=[{file-parser, engine:
  native}]``. Used for the head-to-head "is the model good enough on
  its own?" measurement.
* ``SurfSenseArm`` — POST ``/api/v1/new_chat`` with the question
  scoped to the relevant ``mentioned_document_ids``; consume the SSE
  stream and parse citations.

Both implement the same protocol so a benchmark runner only sees
``Arm.answer(request) -> ArmResult``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass
class ArmRequest:
    """One arm-call worth of input.

    * ``question_id`` is opaque — used for logging and joining results.
    * ``prompt`` is the fully-formatted text the arm should send. The
      runner is responsible for prompt construction so head-to-head
      comparisons use byte-identical text.
    * ``pdf_paths`` is the per-question source PDFs (used by
      ``NativePdfArm``). Empty for retrieval-only / corpus-wide
      benchmarks.
    * ``mentioned_document_ids`` is the SurfSense document scoping list
      (used by ``SurfSenseArm``). When ``None`` SurfSense retrieves
      across the whole search space.
    * ``options`` is a free-form bag of arm-specific overrides
      (e.g. SurfSense's ``disabled_tools``).
    """

    question_id: str
    prompt: str
    pdf_paths: list[Path] = field(default_factory=list)
    mentioned_document_ids: list[int] | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class ArmResult:
    """Outcome of one ``Arm.answer`` invocation."""

    arm: str
    question_id: str
    raw_text: str
    answer_letter: str | None = None
    citations: list[dict[str, Any]] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cost_micros: int = 0
    latency_ms: int = 0
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_jsonl(self) -> dict[str, Any]:
        """Stable dict shape for ``data/<suite>/runs/<ts>/<bench>_raw.jsonl``."""

        return {
            "arm": self.arm,
            "question_id": self.question_id,
            "answer_letter": self.answer_letter,
            "raw_text": self.raw_text,
            "citations": self.citations,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_micros": self.cost_micros,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "extra": self.extra,
        }


class Arm(Protocol):
    """One concrete way to answer questions for a given run."""

    name: str

    async def answer(self, request: ArmRequest) -> ArmResult:  # pragma: no cover - protocol
        ...
