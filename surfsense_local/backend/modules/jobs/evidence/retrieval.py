"""Which passages a question is shown: all of them when they fit the model's window, else the best by BM25.

Lexical and in memory, so a run on this computer and an eval run choose the same
passages; the app's semantic search can stand in later behind the same call.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from modules.jobs.evidence.passages import Passage

_STOP = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "do",
        "does",
        "for",
        "from",
        "has",
        "have",
        "how",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "their",
        "them",
        "they",
        "this",
        "to",
        "was",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "will",
        "with",
        "you",
        "your",
        "yours",
        "our",
        "we",
        "any",
        "all",
        "such",
    ]
)
_SUFFIXES = (
    "ations",
    "ation",
    "ions",
    "ion",
    "ings",
    "ing",
    "ies",
    "ied",
    "es",
    "ed",
    "s",
)
# BM25's usual constants.
_K1 = 1.5
_B = 0.75


def terms(text: str) -> list[str]:
    found = []
    for word in re.findall(r"[^\W_]+", text.casefold()):
        if word in _STOP:
            continue
        for suffix in _SUFFIXES:
            if word.endswith(suffix) and len(word) - len(suffix) >= 4:
                word = word[: -len(suffix)]
                break
        found.append(word)
    return found


@dataclass
class Retriever:
    passages: list[Passage]
    # Characters of passages the prompt may hold; past it, each question gets its best few.
    budget_chars: int
    per_question: int = 8

    def __post_init__(self) -> None:
        self._bags = [Counter(terms(f"{p.section} {p.text}")) for p in self.passages]
        lengths = [sum(bag.values()) for bag in self._bags]
        self._average = sum(lengths) / len(lengths) if lengths else 0.0
        self._lengths = lengths
        documents = Counter(term for bag in self._bags for term in bag)
        count = len(self._bags)
        self._idf = {
            term: math.log(1 + (count - seen + 0.5) / (seen + 0.5))
            for term, seen in documents.items()
        }

    @property
    def whole(self) -> bool:
        return sum(len(p.text) for p in self.passages) <= self.budget_chars

    def for_question(self, question: str) -> list[int]:
        """Indexes into `passages`, in source order, so neighbours read as they were written."""
        if self.whole:
            return list(range(len(self.passages)))
        wanted = terms(question)
        scored = sorted(
            ((self._score(i, wanted), i) for i in range(len(self.passages))),
            reverse=True,
        )
        best = [i for score, i in scored[: self.per_question] if score > 0]
        return sorted(best)

    def _score(self, index: int, wanted: list[str]) -> float:
        bag = self._bags[index]
        length = self._lengths[index] or 1
        score = 0.0
        for term in set(wanted):
            frequency = bag.get(term, 0)
            if not frequency:
                continue
            norm = (
                frequency
                * (_K1 + 1)
                / (frequency + _K1 * (1 - _B + _B * length / (self._average or 1)))
            )
            score += self._idf.get(term, 0.0) * norm
        return score
