"""Format-aware grader for MMLongBench-Doc answers.

The dataset ships with five ``answer_format`` values per question:

* ``Str``  — short factoid string
* ``Int``  — integer count / year
* ``Float`` — decimal number (often with units stripped)
* ``List`` — comma- or semicolon-separated bag of items
* ``None`` — gold answer is literally "Not answerable" (hallucination probe)

The official MMLongBench-Doc paper grades with GPT-4 as judge. We
implement a *deterministic* rule-based grader as the default (so two
researchers running the same harness get the same number); an
LLM-judge mode is exposed via ``--judge gpt5`` and routed through the
same OpenRouter key the arms use, but is opt-in to keep cost down.

Returned by every grading call:

* ``correct: bool`` — final pass/fail used for accuracy + McNemar
* ``f1: float``     — token-level F1 (continuous credit, useful when
  comparing arms that get *most* of a list right)
* ``method: str``   — which path graded the row (one of
  ``str_norm`` / ``int_eq`` / ``float_tol`` / ``list_set`` /
  ``none_match`` / ``llm_judge``).
"""

from __future__ import annotations

import re
import string
from collections import Counter
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass
class GradeResult:
    correct: bool
    f1: float
    method: str
    normalised_pred: str = ""
    normalised_gold: str = ""


# ---------------------------------------------------------------------------
# Normalisation helpers (shared)
# ---------------------------------------------------------------------------

_PUNCT_TABLE = str.maketrans({c: " " for c in string.punctuation})
_ARTICLES = re.compile(r"\b(a|an|the)\b", re.IGNORECASE)
_WS = re.compile(r"\s+")
_NOT_ANSWERABLE_TOKENS = {
    "not answerable",
    "cannot be answered",
    "cannot answer",
    "no answer",
    "unknown",
    "none",
    "not specified",
    "not mentioned",
    "not provided",
    "the answer is not in the document",
}

# Abbreviations that should be matched literally on the lowercased
# prediction (because normalisation strips their punctuation and
# leaves them too short to be safe as substring tokens).
_NOT_ANSWERABLE_LITERAL = {"n/a", "na/", "n.a.", "n a"}


def _normalise_text(s: str) -> str:
    """SQuAD-style normalisation: lowercase, drop punctuation/articles, squash whitespace."""

    s = s.lower()
    s = s.translate(_PUNCT_TABLE)
    s = _ARTICLES.sub(" ", s)
    s = _WS.sub(" ", s).strip()
    return s


# ---------------------------------------------------------------------------
# Per-format graders
# ---------------------------------------------------------------------------


def _grade_str(pred: str, gold: str) -> GradeResult:
    p = _normalise_text(pred)
    g = _normalise_text(gold)
    if not p:
        return GradeResult(False, 0.0, "str_norm", p, g)
    if p == g:
        return GradeResult(True, 1.0, "str_norm", p, g)
    # Substring match in either direction = correct (handles the common
    # "model emits a fuller sentence containing the gold" case).
    if g and (g in p or p in g):
        return GradeResult(True, _f1_tokens(p, g), "str_norm", p, g)
    return GradeResult(False, _f1_tokens(p, g), "str_norm", p, g)


_INT_RE = re.compile(r"-?\d[\d,]*")


def _grade_int(pred: str, gold: str) -> GradeResult:
    g_match = _INT_RE.search(gold)
    if g_match is None:
        return _grade_str(pred, gold)
    g_val = int(g_match.group(0).replace(",", ""))
    p_match = _INT_RE.search(pred)
    if p_match is None:
        return GradeResult(False, 0.0, "int_eq", str(p_match), str(g_val))
    p_val = int(p_match.group(0).replace(",", ""))
    return GradeResult(
        p_val == g_val, 1.0 if p_val == g_val else 0.0, "int_eq", str(p_val), str(g_val)
    )


_FLOAT_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


def _grade_float(pred: str, gold: str, *, rel_tol: float = 1e-2) -> GradeResult:
    g_match = _FLOAT_RE.search(gold)
    if g_match is None:
        return _grade_str(pred, gold)
    g_val = float(g_match.group(0).replace(",", "."))
    p_match = _FLOAT_RE.search(pred)
    if p_match is None:
        return GradeResult(False, 0.0, "float_tol", "", str(g_val))
    p_val = float(p_match.group(0).replace(",", "."))
    # Tolerance: 1% relative or 0.01 absolute, whichever is looser.
    abs_diff = abs(p_val - g_val)
    tol = max(abs(g_val) * rel_tol, 0.01)
    ok = abs_diff <= tol
    return GradeResult(ok, 1.0 if ok else 0.0, "float_tol", str(p_val), str(g_val))


_LIST_SPLIT = re.compile(r"[;,\n]")


def _grade_list(pred: str, gold: str) -> GradeResult:
    g_items = {_normalise_text(x) for x in _LIST_SPLIT.split(gold) if x.strip()}
    p_items = {_normalise_text(x) for x in _LIST_SPLIT.split(pred) if x.strip()}
    if not g_items:
        return _grade_str(pred, gold)
    inter = g_items & p_items
    if not inter:
        return GradeResult(
            False, 0.0, "list_set", ", ".join(sorted(p_items)), ", ".join(sorted(g_items))
        )
    precision = len(inter) / len(p_items) if p_items else 0.0
    recall = len(inter) / len(g_items)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return GradeResult(
        f1 >= 0.999, f1, "list_set", ", ".join(sorted(p_items)), ", ".join(sorted(g_items))
    )


def _grade_none(pred: str, gold: str) -> GradeResult:
    """Gold == 'Not answerable'. The arm earns credit if its prediction
    expresses inability to answer.

    Two passes:

    1. Literal-substring check on the lowercased+stripped pred for
       ambiguous abbreviations like ``n/a`` (since normalisation
       strips the punctuation and would over-match).
    2. Word-boundary substring check on the normalised pred for the
       multi-word phrases (``cannot answer``, ``not specified`` etc.).
    """

    raw_lower = (pred or "").strip().lower()
    p = _normalise_text(pred)
    expressed_unknown = False

    # Pass 1: literal abbreviation hits on the raw lowercased text.
    if any(lit in raw_lower for lit in _NOT_ANSWERABLE_LITERAL):
        expressed_unknown = True

    # Pass 2: word-boundary check on normalised tokens.
    if not expressed_unknown:
        p_padded = f" {p} "
        for tok_raw in _NOT_ANSWERABLE_TOKENS:
            tok = _normalise_text(tok_raw)
            if not tok or len(tok) < 3:
                continue
            if f" {tok} " in p_padded:
                expressed_unknown = True
                break
    return GradeResult(
        expressed_unknown,
        1.0 if expressed_unknown else 0.0,
        "none_match",
        p,
        _normalise_text(gold),
    )


def _f1_tokens(pred: str, gold: str) -> float:
    p_tok = pred.split()
    g_tok = gold.split()
    if not p_tok or not g_tok:
        return 0.0
    common = Counter(p_tok) & Counter(g_tok)
    overlap = sum(common.values())
    if overlap == 0:
        return 0.0
    precision = overlap / len(p_tok)
    recall = overlap / len(g_tok)
    return 2 * precision * recall / (precision + recall)


# ---------------------------------------------------------------------------
# Public dispatcher
# ---------------------------------------------------------------------------


_FORMAT_DISPATCH = {
    "str": _grade_str,
    "int": _grade_int,
    "float": _grade_float,
    "list": _grade_list,
    "none": _grade_none,
}


def grade(*, pred: str, gold: str, answer_format: str) -> GradeResult:
    """Grade a single (prediction, gold) pair.

    ``answer_format`` is the dataset's ``answer_format`` column value.
    Unknown / blank values fall through to string grading.
    """

    fmt = (answer_format or "").strip().lower()
    fn = _FORMAT_DISPATCH.get(fmt, _grade_str)
    return fn(pred or "", gold or "")


__all__ = ["GradeResult", "grade"]
