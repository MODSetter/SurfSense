"""FRAMES grader: deterministic shortcut + LLM-as-judge fallback.

FRAMES gold answers are short factoids (a name, a year, an ordinal,
a count). The published paper uses an LLM judge for grading, citing
the long tail of paraphrasing ("Jane Ballou" vs "Mrs. Ballou (Jane)";
"5" vs "five"; "London, England" vs "London"). We replicate that
faithfully *but* avoid burning judge tokens on the obvious cases.

Pipeline per (pred, gold):

1. Normalise both sides (SQuAD-style).
2. If normalised pred == normalised gold → CORRECT (``method=exact``).
3. Numeric path: if both extract to a single number and the values
   match within 1% relative tolerance → CORRECT (``method=numeric``).
4. Substring path: if normalised gold appears as a *whole-word phrase*
   inside normalised pred (or vice versa) → CORRECT
   (``method=substring``).
5. Otherwise → call the LLM judge if a judge is wired; the judge
   returns yes/no with a one-line rationale.
6. If no judge is configured, fall through to ``False``
   (``method=lexical_miss``).

The judge is called *concurrently* across the run via a semaphore (so
it doesn't outrun the upstream rate limit). Cached on
``(arm, qid)`` so re-running ``report`` doesn't re-judge.

Returned shape mirrors ``mmlongbench.grader.GradeResult`` to keep
report writers uniform across benchmarks.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import string
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ....core.providers.openrouter_chat import OpenRouterChatProvider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass
class GradeResult:
    """Shape mirrors mmlongbench.grader.GradeResult for report uniformity."""

    correct: bool
    f1: float
    method: str
    normalised_pred: str = ""
    normalised_gold: str = ""
    judge_rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "correct": self.correct,
            "f1": self.f1,
            "method": self.method,
            "normalised_pred": self.normalised_pred,
            "normalised_gold": self.normalised_gold,
            "judge_rationale": self.judge_rationale,
        }


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------


_PUNCT_TABLE = str.maketrans({c: " " for c in string.punctuation})
_ARTICLES = re.compile(r"\b(a|an|the)\b", re.IGNORECASE)
_WS = re.compile(r"\s+")


def _normalise(s: str) -> str:
    s = (s or "").lower()
    s = s.translate(_PUNCT_TABLE)
    s = _ARTICLES.sub(" ", s)
    s = _WS.sub(" ", s).strip()
    return s


_WORD_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
}

_NUMERIC_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


def _maybe_number(s: str) -> float | None:
    """Extract a single numeric value, recognising digit and word forms.

    Operates on the lowercased *raw* text (rather than the
    punctuation-stripped normalisation) so that thousands separators
    like ``1,234`` are preserved through the regex and parsed
    correctly. We only fall back to ``_normalise`` for the word-number
    pass, which doesn't care about punctuation.
    """

    raw = (s or "").strip().lower()
    if not raw:
        return None
    match = _NUMERIC_RE.search(raw)
    if match:
        try:
            return float(match.group(0).replace(",", ""))
        except ValueError:
            pass
    for tok in _normalise(s).split():
        if tok in _WORD_NUMBERS:
            return float(_WORD_NUMBERS[tok])
    return None


def _whole_word_substring(haystack: str, needle: str) -> bool:
    """Is ``needle`` present as a whole-word phrase in ``haystack``?"""

    if not needle:
        return False
    pad_h = f" {haystack} "
    pad_n = f" {needle} "
    return pad_n in pad_h


# ---------------------------------------------------------------------------
# Deterministic shortcut
# ---------------------------------------------------------------------------


def grade_deterministic(*, pred: str, gold: str) -> GradeResult:
    """Try to grade without the LLM judge. Returns a final-result object.

    A ``False`` result with ``method == "lexical_miss"`` is the signal
    to the caller that the LLM judge should be consulted (if available).
    """

    if not (pred or "").strip():
        return GradeResult(False, 0.0, "empty_pred", "", _normalise(gold))

    p = _normalise(pred)
    g = _normalise(gold)
    if not g:
        # Defensively: gold should never be empty; if it is, we can't grade.
        return GradeResult(False, 0.0, "empty_gold", p, g)

    if p == g:
        return GradeResult(True, 1.0, "exact", p, g)

    p_num = _maybe_number(pred)
    g_num = _maybe_number(gold)
    if p_num is not None and g_num is not None:
        # 1% relative tolerance, 0.5 absolute floor (handles year-ish answers).
        tol = max(abs(g_num) * 0.01, 0.5)
        if abs(p_num - g_num) <= tol:
            return GradeResult(True, 1.0, "numeric", p, g)
        return GradeResult(False, 0.0, "numeric_miss", p, g)

    if _whole_word_substring(p, g):
        return GradeResult(True, 1.0, "substring", p, g)
    if _whole_word_substring(g, p) and len(p) >= 3:
        # Be conservative the other direction — only credit if pred is
        # at least 3 normalised chars (avoids "John" matching gold
        # "John F. Kennedy" as correct).
        return GradeResult(True, 1.0, "substring_reverse", p, g)

    return GradeResult(False, 0.0, "lexical_miss", p, g)


# ---------------------------------------------------------------------------
# LLM-as-judge
# ---------------------------------------------------------------------------


_JUDGE_SYSTEM = (
    "You are an impartial grader for short-answer factual questions. "
    "Given a question, the gold answer, and a model's prediction, "
    "decide whether the prediction is correct. The prediction is "
    "correct if it expresses the same factual content as the gold "
    "answer, allowing for paraphrasing, surface-level differences "
    "(numbers as words, names with/without titles), and additional "
    "non-contradictory detail. The prediction is incorrect if it "
    "expresses a different fact, omits the central answer, or hedges "
    "without committing.\n\n"
    "Respond with ONLY a JSON object on a single line:\n"
    '{\"correct\": true|false, \"rationale\": \"<one short sentence>\"}'
)


_JUDGE_TEMPLATE = """\
Question: {question}
Gold answer: {gold}
Model prediction: {pred}

Decide whether the prediction is correct.
"""


@dataclass
class JudgeConfig:
    """Configuration handed to ``LlmJudge`` at construction time."""

    api_key: str
    model: str = "anthropic/claude-sonnet-4.5"
    base_url: str = "https://openrouter.ai/api/v1"
    max_tokens: int = 200
    concurrency: int = 4


class LlmJudge:
    """Async LLM judge over OpenRouter chat completions."""

    def __init__(self, *, config: JudgeConfig) -> None:
        self._config = config
        self._provider = OpenRouterChatProvider(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
        )
        self._sem = asyncio.Semaphore(max(1, config.concurrency))

    @property
    def model(self) -> str:
        return self._config.model

    async def judge(
        self,
        *,
        question: str,
        gold: str,
        pred: str,
    ) -> tuple[bool, str]:
        """Return ``(is_correct, rationale)``. Errors return False + reason."""

        prompt = _JUDGE_TEMPLATE.format(question=question, gold=gold, pred=pred)
        try:
            async with self._sem:
                response = await self._provider.complete(
                    prompt=prompt,
                    system_prompt=_JUDGE_SYSTEM,
                    max_tokens=self._config.max_tokens,
                )
        except Exception as exc:  # noqa: BLE001
            return False, f"judge_error: {type(exc).__name__}: {exc}"
        return _parse_judge_response(response.text)


def _parse_judge_response(text: str) -> tuple[bool, str]:
    """Pull ``correct`` + ``rationale`` out of the judge's reply."""

    if not text or not text.strip():
        return False, "judge_returned_empty"
    # Accept JSON anywhere in the message; some models prepend prose.
    match = re.search(r"\{[^{}]*\}", text, flags=re.DOTALL)
    candidate = match.group(0) if match else text
    try:
        data = json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        # Fallback: yes/no parsing.
        lowered = text.strip().lower()
        if lowered.startswith("yes") or "correct: yes" in lowered or '"correct": true' in lowered:
            return True, "yes (parser_fallback)"
        if lowered.startswith("no") or "correct: no" in lowered or '"correct": false' in lowered:
            return False, "no (parser_fallback)"
        return False, f"unparseable_judge_response: {text[:200]}"
    correct = bool(data.get("correct"))
    rationale = str(data.get("rationale", "")).strip()[:280]
    return correct, rationale


# ---------------------------------------------------------------------------
# Combined grader
# ---------------------------------------------------------------------------


async def grade_with_judge(
    *,
    pred: str,
    gold: str,
    question: str,
    judge: LlmJudge | None,
) -> GradeResult:
    """Grade one row: deterministic shortcut → optional LLM judge fallback."""

    det = grade_deterministic(pred=pred, gold=gold)
    if det.correct or det.method != "lexical_miss":
        return det
    if judge is None:
        return det
    is_correct, rationale = await judge.judge(question=question, gold=gold, pred=pred)
    return GradeResult(
        correct=is_correct,
        f1=1.0 if is_correct else 0.0,
        method="llm_judge",
        normalised_pred=det.normalised_pred,
        normalised_gold=det.normalised_gold,
        judge_rationale=rationale,
    )


async def grade_many(
    *,
    rows: Sequence[tuple[str, str, str, str]],
    judge: LlmJudge | None,
) -> list[GradeResult]:
    """Grade ``[(qid, question, gold, pred), ...]`` concurrently.

    The judge already enforces its own concurrency cap; this just
    schedules everything via ``asyncio.gather``. ``qid`` is unused
    inside the grader but threaded through so callers can correlate
    results back to their rows.
    """

    if not rows:
        return []
    coros = [
        grade_with_judge(pred=p, gold=g, question=q, judge=judge)
        for _qid, q, g, p in rows
    ]
    return list(await asyncio.gather(*coros))


__all__ = [
    "GradeResult",
    "JudgeConfig",
    "LlmJudge",
    "grade_deterministic",
    "grade_many",
    "grade_with_judge",
]
