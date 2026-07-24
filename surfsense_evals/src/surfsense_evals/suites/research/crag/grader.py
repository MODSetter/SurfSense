"""CRAG 3-class grader: ``correct`` (+1) / ``missing`` (0) / ``incorrect`` (-1).

The CRAG paper's headline metric is the **Truthfulness Score**:

    score = (#correct - #incorrect) / total

which rewards calibrated abstention — refusing to answer is neutral
(0), guessing wrong is negative (-1). Grading is therefore a 3-class
problem rather than the 2-class accuracy used for FRAMES.

Pipeline per (pred, gold, alt_ans, question_type):

1. Detect refusal first (``Answer: I don't know`` / "I don't know" /
   "no information") → ``missing`` (deterministic, never billed).
2. ``false_premise`` questions: gold is canonically "the question
   contains a false premise" — reward any answer that flags the
   false premise (substring "false premise" / "incorrect premise" /
   "no such") as correct.
3. Run the FRAMES-style deterministic shortcut (exact / numeric /
   substring) on ``pred`` against ``gold ∪ alt_ans``. Hit → correct.
4. Fall through to the LLM judge (if configured), which returns one
   of ``{correct, missing, incorrect}`` — verbatim CRAG protocol.
5. No judge configured → record ``incorrect`` (pessimistic but at
   least monotone with the deterministic grader).

The judge is throttled by an asyncio.Semaphore so it doesn't outrun
the OpenRouter rate limit; the pre-judge deterministic pass keeps
the bill bounded (most easy "Beyoncé"-vs-"Beyoncé Knowles" cases
short-circuit before we burn judge tokens).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import string
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from ....core.providers.openrouter_chat import OpenRouterChatProvider

logger = logging.getLogger(__name__)


GradeClass = Literal["correct", "missing", "incorrect"]


# ---------------------------------------------------------------------------
# Public type
# ---------------------------------------------------------------------------


@dataclass
class CragGradeResult:
    """One graded (pred, gold) pair under CRAG's 3-class rubric."""

    grade: GradeClass
    score: int  # +1 / 0 / -1
    method: str  # exact, numeric, substring, refusal,
    # false_premise_correct, false_premise_miss,
    # llm_judge, lexical_miss, ...
    normalised_pred: str = ""
    normalised_gold: str = ""
    judge_rationale: str = ""

    @property
    def correct(self) -> bool:
        return self.grade == "correct"

    @property
    def missing(self) -> bool:
        return self.grade == "missing"

    @property
    def incorrect(self) -> bool:
        return self.grade == "incorrect"

    def to_dict(self) -> dict[str, Any]:
        return {
            "grade": self.grade,
            "score": self.score,
            "method": self.method,
            "normalised_pred": self.normalised_pred,
            "normalised_gold": self.normalised_gold,
            "judge_rationale": self.judge_rationale,
        }


def _grade_to_score(grade: GradeClass) -> int:
    return {"correct": 1, "missing": 0, "incorrect": -1}[grade]


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
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}

_NUMERIC_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


def _maybe_number(s: str) -> float | None:
    """Extract a single numeric value from raw lowercased text."""

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
    if not needle:
        return False
    return f" {needle} " in f" {haystack} "


# ---------------------------------------------------------------------------
# Refusal detection
# ---------------------------------------------------------------------------


_REFUSAL_PATTERNS = [
    re.compile(r"\bi\s+don'?t\s+know\b", re.IGNORECASE),
    re.compile(r"\bi\s+do\s+not\s+know\b", re.IGNORECASE),
    re.compile(r"\bnot\s+enough\s+information\b", re.IGNORECASE),
    re.compile(r"\binsufficient\s+information\b", re.IGNORECASE),
    re.compile(r"\bcannot\s+(?:be\s+)?(?:answered|determined)\b", re.IGNORECASE),
    re.compile(r"\bunable\s+to\s+(?:answer|determine)\b", re.IGNORECASE),
    re.compile(r"\bno\s+(?:information|data|evidence)\b", re.IGNORECASE),
]


def _is_refusal(pred: str) -> bool:
    """Cheap deterministic check for "I don't know" -shaped responses."""

    if not pred or not pred.strip():
        return True  # empty answer is a de facto refusal
    return any(p.search(pred) for p in _REFUSAL_PATTERNS)


# ---------------------------------------------------------------------------
# False-premise handling
# ---------------------------------------------------------------------------


_FALSE_PREMISE_PATTERNS = [
    re.compile(r"false\s+premise", re.IGNORECASE),
    re.compile(r"incorrect\s+premise", re.IGNORECASE),
    re.compile(r"premise\s+(?:is|of)\s+the\s+question", re.IGNORECASE),
    re.compile(r"\bno\s+such\b", re.IGNORECASE),
    re.compile(r"never\s+(?:happened|occurred|existed)", re.IGNORECASE),
    re.compile(r"\bdid\s+not\s+(?:happen|occur|exist)\b", re.IGNORECASE),
    re.compile(r"\bdoes\s+not\s+exist\b", re.IGNORECASE),
    re.compile(r"is\s+not\s+(?:true|correct|accurate)", re.IGNORECASE),
    re.compile(r"\bisn'?t\s+(?:true|correct|accurate)\b", re.IGNORECASE),
    re.compile(r"\binvalid\s+(?:premise|question|assumption)\b", re.IGNORECASE),
]


def _flags_false_premise(pred: str) -> bool:
    return any(p.search(pred) for p in _FALSE_PREMISE_PATTERNS)


# ---------------------------------------------------------------------------
# Deterministic grader
# ---------------------------------------------------------------------------


def grade_deterministic(
    *,
    pred: str,
    gold: str,
    alt_answers: Sequence[str] = (),
    question_type: str = "",
) -> CragGradeResult:
    """Try to grade without the LLM judge. Returns a final result.

    Always returns *some* result — the caller checks ``method`` to
    decide whether the LLM judge should overturn it. ``lexical_miss``
    and ``false_premise_unclear`` are the two methods that trigger the
    judge fallback.
    """

    qtype = (question_type or "").lower()
    n_pred = _normalise(pred)
    n_gold = _normalise(gold)

    if _is_refusal(pred):
        # CRAG protocol: refusal is *missing* (0), even on false-premise
        # questions where one might argue refusal == correct. We
        # follow the paper's grading literally.
        return CragGradeResult(
            grade="missing",
            score=0,
            method="refusal",
            normalised_pred=n_pred,
            normalised_gold=n_gold,
        )

    # Empty-gold guard (shouldn't happen, but defensively):
    if not n_gold:
        return CragGradeResult(
            grade="incorrect",
            score=-1,
            method="empty_gold",
            normalised_pred=n_pred,
            normalised_gold=n_gold,
        )

    # False-premise questions: gold is typically "the question contains
    # a false premise" / "no such X" / similar. Any answer that
    # explicitly flags the false premise is correct.
    if qtype == "false_premise":
        if _flags_false_premise(pred):
            return CragGradeResult(
                grade="correct",
                score=1,
                method="false_premise_flagged",
                normalised_pred=n_pred,
                normalised_gold=n_gold,
            )
        # If the model commits to *any* concrete answer on a false-
        # premise question without flagging the premise, it is wrong.
        # But we don't classify ourselves — let the judge decide on
        # the off chance the gold itself is e.g. "no" and the pred
        # is "no" without explicit "false premise" wording.
        return CragGradeResult(
            grade="incorrect",
            score=-1,
            method="false_premise_unclear",
            normalised_pred=n_pred,
            normalised_gold=n_gold,
        )

    # All non-false-premise questions: try the standard chain against
    # gold and each alt answer. First match wins.
    candidates = [gold, *list(alt_answers)]
    for candidate in candidates:
        if not candidate or not str(candidate).strip():
            continue
        cand_norm = _normalise(candidate)
        if not cand_norm:
            continue
        if n_pred == cand_norm:
            return CragGradeResult(
                grade="correct",
                score=1,
                method="exact",
                normalised_pred=n_pred,
                normalised_gold=cand_norm,
            )
        p_num = _maybe_number(pred)
        c_num = _maybe_number(candidate)
        if p_num is not None and c_num is not None:
            # Pure 1% relative tolerance for CRAG (currency, counts,
            # ratios). Unlike FRAMES (which uses a 0.5 absolute floor
            # for year-shaped answers), CRAG's numeric questions are
            # often small-value (stock prices, percentages) where a
            # 0.5 floor would let "$2.05" match "$2.17". The judge is
            # the safety net for borderline rounding cases.
            tol = abs(c_num) * 0.01
            if abs(p_num - c_num) <= tol:
                return CragGradeResult(
                    grade="correct",
                    score=1,
                    method="numeric",
                    normalised_pred=n_pred,
                    normalised_gold=cand_norm,
                )
            # Numeric question with different numbers — keep looking
            # at other candidates rather than declaring miss now;
            # alt answers may include word forms that pass.
        if _whole_word_substring(n_pred, cand_norm):
            return CragGradeResult(
                grade="correct",
                score=1,
                method="substring",
                normalised_pred=n_pred,
                normalised_gold=cand_norm,
            )
        if _whole_word_substring(cand_norm, n_pred) and len(n_pred) >= 3:
            return CragGradeResult(
                grade="correct",
                score=1,
                method="substring_reverse",
                normalised_pred=n_pred,
                normalised_gold=cand_norm,
            )

    return CragGradeResult(
        grade="incorrect",
        score=-1,
        method="lexical_miss",
        normalised_pred=n_pred,
        normalised_gold=n_gold,
    )


# ---------------------------------------------------------------------------
# LLM-as-judge (3-class)
# ---------------------------------------------------------------------------


_JUDGE_SYSTEM = (
    "You are an impartial grader for short-answer factual questions, "
    "following the CRAG benchmark rubric. Given a question, the gold "
    "answer (and any alternative valid answers), and a model's "
    "prediction, classify the prediction into exactly one of three "
    "categories:\n\n"
    '* "correct"   — the prediction expresses the same factual '
    "content as the gold answer (paraphrasing OK; numbers as words "
    "OK; partial-but-correct names OK; non-contradictory extra "
    "detail OK).\n"
    '* "missing"   — the prediction explicitly refuses, says "I '
    "don't know\", says there is insufficient information, or hedges "
    "without committing.\n"
    '* "incorrect" — the prediction commits to a fact that is '
    "different from the gold answer, or fails to flag a false "
    "premise when the question contains one.\n\n"
    "Special case: if the question contains a false premise and the "
    "gold answer says so, then a prediction that flags the false "
    'premise is "correct".\n\n'
    "Respond with ONLY a JSON object on a single line:\n"
    '{"grade": "correct"|"missing"|"incorrect", "rationale": "<one short sentence>"}'
)


_JUDGE_TEMPLATE = """\
Question: {question}
Question type: {question_type}
Gold answer: {gold}
{alt_block}Model prediction: {pred}

Decide whether the prediction is correct, missing, or incorrect.
"""


@dataclass
class CragJudgeConfig:
    api_key: str
    model: str = "anthropic/claude-sonnet-4.5"
    base_url: str = "https://openrouter.ai/api/v1"
    max_tokens: int = 200
    concurrency: int = 4


class CragLlmJudge:
    """Async LLM judge over OpenRouter chat completions, 3-class output."""

    def __init__(self, *, config: CragJudgeConfig) -> None:
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
        alt_answers: Sequence[str],
        pred: str,
        question_type: str = "",
    ) -> tuple[GradeClass, str]:
        """Return ``(grade, rationale)``. Errors return incorrect + reason."""

        alt_block = ""
        if alt_answers:
            alt_lines = "\n".join(f"  - {a}" for a in alt_answers if a)
            if alt_lines:
                alt_block = f"Alternative valid answers:\n{alt_lines}\n"
        prompt = _JUDGE_TEMPLATE.format(
            question=question,
            question_type=question_type or "unknown",
            gold=gold,
            alt_block=alt_block,
            pred=pred,
        )
        try:
            async with self._sem:
                response = await self._provider.complete(
                    prompt=prompt,
                    system_prompt=_JUDGE_SYSTEM,
                    max_tokens=self._config.max_tokens,
                )
        except Exception as exc:  # noqa: BLE001
            return "incorrect", f"judge_error: {type(exc).__name__}: {exc}"
        return _parse_judge_response(response.text)


def _parse_judge_response(text: str) -> tuple[GradeClass, str]:
    """Parse the judge reply into a 3-class label + rationale."""

    if not text or not text.strip():
        return "incorrect", "judge_returned_empty"
    match = re.search(r"\{[^{}]*\}", text, flags=re.DOTALL)
    candidate = match.group(0) if match else text
    try:
        data = json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        lowered = text.strip().lower()
        if "correct" in lowered and "incorrect" not in lowered:
            return "correct", "yes (parser_fallback)"
        if "missing" in lowered or "i don" in lowered:
            return "missing", "missing (parser_fallback)"
        return "incorrect", f"unparseable_judge_response: {text[:200]}"
    raw_grade = str(data.get("grade") or "").strip().lower()
    rationale = str(data.get("rationale", "")).strip()[:280]
    if raw_grade in {"correct", "missing", "incorrect"}:
        return raw_grade, rationale  # type: ignore[return-value]
    return "incorrect", f"unknown_grade={raw_grade!r}; {rationale}"


# ---------------------------------------------------------------------------
# Combined grader
# ---------------------------------------------------------------------------


# Methods that should *not* trigger the LLM judge — the deterministic
# verdict is conclusive (refusal, exact match, numeric mismatch, etc.).
_TERMINAL_METHODS = frozenset(
    {
        "refusal",
        "exact",
        "numeric",
        "substring",
        "substring_reverse",
        "false_premise_flagged",
        "empty_gold",
    }
)


async def grade_with_judge(
    *,
    pred: str,
    gold: str,
    alt_answers: Sequence[str],
    question: str,
    question_type: str,
    judge: CragLlmJudge | None,
) -> CragGradeResult:
    """One row → deterministic shortcut → optional LLM judge fallback."""

    det = grade_deterministic(
        pred=pred,
        gold=gold,
        alt_answers=alt_answers,
        question_type=question_type,
    )
    if det.method in _TERMINAL_METHODS:
        return det
    if judge is None:
        return det  # ``lexical_miss`` / ``false_premise_unclear`` → keep as-is
    grade, rationale = await judge.judge(
        question=question,
        gold=gold,
        alt_answers=alt_answers,
        pred=pred,
        question_type=question_type,
    )
    return CragGradeResult(
        grade=grade,
        score=_grade_to_score(grade),
        method="llm_judge",
        normalised_pred=det.normalised_pred,
        normalised_gold=det.normalised_gold,
        judge_rationale=rationale,
    )


@dataclass
class CragGradeRow:
    """One row to grade. Mirrors the FRAMES grader's tuple but typed."""

    qid: str
    question: str
    gold: str
    alt_answers: list[str]
    pred: str
    question_type: str = ""


async def grade_many(
    *,
    rows: Sequence[CragGradeRow],
    judge: CragLlmJudge | None,
) -> list[CragGradeResult]:
    """Grade every row concurrently. Judge enforces its own concurrency cap."""

    if not rows:
        return []
    coros = [
        grade_with_judge(
            pred=r.pred,
            gold=r.gold,
            alt_answers=r.alt_answers,
            question=r.question,
            question_type=r.question_type,
            judge=judge,
        )
        for r in rows
    ]
    return list(await asyncio.gather(*coros))


__all__ = [
    "CragGradeResult",
    "CragGradeRow",
    "CragJudgeConfig",
    "CragLlmJudge",
    "GradeClass",
    "grade_deterministic",
    "grade_many",
    "grade_with_judge",
]
