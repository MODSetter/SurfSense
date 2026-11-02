"""Which passages a question is shown: all of them when they fit the model's window, else the
best by BM25 and, with the app's embedder, by meaning too.

In memory and deterministic, so a run on this computer and an eval run choose the same
passages.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from itertools import zip_longest

import numpy as np

from modules.jobs.evidence.passages import Passage

# Texts to unit vectors, a question's when the flag is True, else passages'.
Embed = Callable[[list[str], bool], list[list[float]]]
# Passages embedded per call.
EMBED_BATCH = 64
# How high in both rankings a standing query's passage must sit to be shown with every question.
STANDING_TOP = 10

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
                # "policies" and "policy" are one term; "ies" alone would leave "polic".
                word = word[: -len(suffix)] + ("y" if suffix in ("ies", "ied") else "")
                break
        found.append(word)
    return found


@dataclass
class Retriever:
    passages: list[Passage]
    # Characters of passages the prompt may hold; past it, each question gets its best few.
    budget_chars: int
    per_question: int = 8
    # The app's embedder, when at hand. Meaning finds what the words miss, such as a
    # "third party" policy for a "supply chain" question; the two rankings take turns.
    embed: Embed | None = None
    # Queries whose best passages every question is shown, such as how the firm approves and
    # reviews its policies: a question about any one policy needs them, in words it never uses.
    standing: tuple[str, ...] = ()
    per_standing: int = 1

    def __post_init__(self) -> None:
        # A policy is named for what it covers, so its title counts in every passage it holds:
        # without it half of CAIQ's Yes answers never saw their deciding passage.
        self._bags = [
            Counter(terms(f"{p.title} {p.section} {p.text}")) for p in self.passages
        ]
        lengths = [sum(bag.values()) for bag in self._bags]
        self._average = sum(lengths) / len(lengths) if lengths else 0.0
        self._lengths = lengths
        documents = Counter(term for bag in self._bags for term in bag)
        count = len(self._bags)
        self._idf = {
            term: math.log(1 + (count - seen + 0.5) / (seen + 0.5))
            for term, seen in documents.items()
        }
        self._vectors: np.ndarray | None = None
        self._standing: list[int] = []
        if self.whole:
            return
        if self.embed is not None and self.passages:
            texts = [f"{p.title} {p.section}\n{p.text}" for p in self.passages]
            # In batches, so an embed that checks for a cancel is asked between them.
            self._vectors = _unit(
                [
                    vector
                    for start in range(0, len(texts), EMBED_BATCH)
                    for vector in self.embed(texts[start : start + EMBED_BATCH], False)
                ]
            )
        for query in self.standing:
            self._standing += self._agreed(query)[: self.per_standing]

    @property
    def whole(self) -> bool:
        return sum(len(p.text) for p in self.passages) <= self.budget_chars

    @property
    def pinned(self) -> list[int]:
        """The standing queries' passages, which every question is shown; none when all are."""
        return sorted(set(self._standing))

    def for_question(self, question: str) -> list[int]:
        """Indexes into `passages`, in source order, so neighbours read as they were written."""
        if self.whole:
            return list(range(len(self.passages)))
        best = self._ranked(question)[: self.per_question]
        return sorted(set(best) | set(self._standing))

    def _ranked(self, text: str) -> list[int]:
        """Passages best first: by BM25, or by BM25's ranking and meaning's in turn."""
        lexical, semantic = self._lanes(text)
        if semantic is None:
            return lexical
        merged: dict[int, None] = {}
        for pair in zip_longest(lexical, semantic):
            merged.update((i, None) for i in pair if i is not None)
        return list(merged)

    def _agreed(self, query: str) -> list[int]:
        """A standing query's passages, best first, only where the evidence for them is strong:
        among the first few of both rankings, or with words alone, holding half the query's
        terms. A weak pick would be shown with every question, so none is better."""
        lexical, semantic = self._lanes(query)
        if semantic is not None:
            near = set(semantic[:STANDING_TOP])
            return [i for i in lexical[:STANDING_TOP] if i in near]
        wanted = set(terms(query))
        return [
            i
            for i in lexical[:STANDING_TOP]
            if len(wanted & self._bags[i].keys()) * 2 >= len(wanted)
        ]

    def _lanes(self, text: str) -> tuple[list[int], list[int] | None]:
        """BM25's ranking of the passages that share a term, and the embedder's of all of them."""
        wanted = terms(text)
        scored = sorted(
            ((self._score(i, wanted), i) for i in range(len(self.passages))),
            reverse=True,
        )
        lexical = [i for score, i in scored if score > 0]
        if self._vectors is None or self.embed is None:
            return lexical, None
        query = _unit(self.embed([text], True))[0]
        return lexical, np.argsort(-(self._vectors @ query), kind="stable").tolist()

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


def _unit(vectors: list[list[float]]) -> np.ndarray:
    """Rows scaled to length 1, so a dot product is the cosine whatever the embedder returns."""
    rows = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(rows, axis=1, keepdims=True)
    return rows / np.where(norms == 0, 1, norms)
