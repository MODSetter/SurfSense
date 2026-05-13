"""Robust extractor for MCQ answer letters.

Handles three answer shapes seen in the wild:

1. **MedRAG envelope** — ``{"step_by_step_thinking": "...", "answer_choice": "A"}``
   embedded somewhere in the assistant message (often inside ```` ```json ```` /
   ``` ``` ``` fences). The regex grabs the JSON object and reads the
   ``answer_choice`` field.

2. **Final-line letter** — e.g. ``Answer: B`` or ``The correct answer is (C).``.
   Falls back to a permissive regex over the last few lines.

3. **Bare letter** — single uppercase letter at the end of the message.

The function returns the parsed letter (uppercased) plus a discriminator
of which strategy fired so the runner / report can flag suspicious
parses (typically zero-confidence parses indicate the model didn't
follow the prompt).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal

ParserStrategy = Literal["json_envelope", "answer_line", "bare_letter", "none"]


@dataclass(frozen=True)
class AnswerLetterResult:
    letter: str | None
    strategy: ParserStrategy

    @property
    def found(self) -> bool:
        return self.letter is not None


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


_JSON_BLOCK = re.compile(r"\{[^{}]*\"answer_choice\"\s*:\s*\"([A-Za-z])\"[^{}]*\}", re.DOTALL)
_FENCED_JSON = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
_ANSWER_LINE = re.compile(
    r"(?:final\s*answer|answer\s*choice|the\s+correct\s+answer\s+is|answer)\s*[:=\-]?\s*"
    r"\(?\s*([A-Za-z])\s*[\)\.]*\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_BARE_LETTER = re.compile(r"^\s*\(?\s*([A-Za-z])\s*[\)\.]*\s*$", re.MULTILINE)


def _from_json_envelope(text: str) -> str | None:
    # Try fenced code blocks first (most likely to contain the JSON).
    for fence in _FENCED_JSON.finditer(text):
        try:
            obj = json.loads(fence.group(1))
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(obj, dict):
            choice = obj.get("answer_choice")
            if isinstance(choice, str) and choice.strip():
                return choice.strip()[:1].upper()

    # Fall back to a tolerant regex over the whole text (handles
    # responses that drop the fences).
    match = _JSON_BLOCK.search(text)
    if match:
        return match.group(1).upper()
    return None


def _from_answer_line(text: str) -> str | None:
    # Walk lines bottom-up; the answer is almost always near the end.
    for match in reversed(list(_ANSWER_LINE.finditer(text))):
        letter = match.group(1).upper()
        if letter.isalpha():
            return letter
    return None


def _from_bare_letter(text: str) -> str | None:
    # Inspect only the final non-empty lines (avoid grabbing in-prose
    # mentions of "A" or "I").
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in reversed(lines[-3:]):
        match = _BARE_LETTER.match(ln)
        if match:
            return match.group(1).upper()
    return None


def extract_answer_letter(text: str) -> AnswerLetterResult:
    """Run strategies in order and return the first hit.

    Order: JSON envelope → final-answer-line regex → bare-letter
    fallback. Empty / whitespace-only text returns
    ``AnswerLetterResult(None, "none")``.
    """

    if not text or not text.strip():
        return AnswerLetterResult(None, "none")

    letter = _from_json_envelope(text)
    if letter:
        return AnswerLetterResult(letter, "json_envelope")

    letter = _from_answer_line(text)
    if letter:
        return AnswerLetterResult(letter, "answer_line")

    letter = _from_bare_letter(text)
    if letter:
        return AnswerLetterResult(letter, "bare_letter")

    return AnswerLetterResult(None, "none")


__all__ = ["AnswerLetterResult", "ParserStrategy", "extract_answer_letter"]
