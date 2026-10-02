"""The bar a model SurfSense did not measure must clear before it is locked.

Ten questions over twenty passages, each answer beside a decoy on the same
topic, and every answer must rank first. Measured on 1 Oct 2026: bge-small and
both curated granite models found 10 of 10. Chat models served as embedders
found 5 to 8, except one at 10, so this proves a model can find answers, which
is what search needs, not that it was built to embed.

A probe alone was not enough: easy paraphrase pairs separated a chat model as
well as bge did.
"""

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

# (question, the passage that answers it, a same-topic passage that does not)
QUESTIONS = (
    (
        "How long does the scanner battery last?",
        "The scanner battery lasts about ten hours on a full charge.",
        "The scanner battery charges in the four-slot cradle.",
    ),
    (
        "When is the invoice due?",
        "Invoices are due thirty days after the date of issue.",
        "Invoices are sent by email as PDF attachments.",
    ),
    (
        "Who approves travel expenses?",
        "Travel expenses are approved by your line manager.",
        "Travel expenses include flights, hotels and meals.",
    ),
    (
        "What temperature should the server room be kept at?",
        "Keep the server room between 18 and 24 degrees Celsius.",
        "The server room is on the second floor next to the lift.",
    ),
    (
        "How many vacation days do new employees get?",
        "New employees receive twenty days of paid vacation per year.",
        "Vacation requests are submitted in the HR portal.",
    ),
    (
        "Where is the spare key for the office?",
        "The spare office key is kept in the reception safe.",
        "The office is locked automatically at 8 pm.",
    ),
    (
        "What does the red warning light mean?",
        "A red warning light means the filter must be replaced.",
        "The warning light is next to the power switch.",
    ),
    (
        "Which port does the database listen on?",
        "The database listens on port 5432 by default.",
        "The database is backed up every night at midnight.",
    ),
    (
        "How do I reset my password?",
        "To reset your password, click Forgot password on the sign-in page.",
        "Passwords must be at least twelve characters long.",
    ),
    (
        "When does the cafeteria close?",
        "The cafeteria closes at three in the afternoon.",
        "The cafeteria serves vegetarian options every day.",
    ),
)


@dataclass(frozen=True)
class SearchCheck:
    first: int
    asked: int

    @property
    def passed(self) -> bool:
        return self.first == self.asked


def search_check(
    embed_queries: Callable[[list[str]], list[list[float]]],
    embed_passages: Callable[[list[str]], list[list[float]]] | None = None,
) -> SearchCheck:
    """How many answers rank first. Questions and passages embed apart, so an
    asymmetric model is checked with its own prefixes."""
    passages = [text for _, answer, decoy in QUESTIONS for text in (answer, decoy)]
    queries = _unit(embed_queries([q for q, _, _ in QUESTIONS]))
    stored = _unit((embed_passages or embed_queries)(passages))
    similarity = queries @ stored.T
    # First means nothing scores above the answer; a tie does not demote it.
    first = sum(
        int(not (similarity[i] > similarity[i, 2 * i]).any())
        for i in range(len(QUESTIONS))
    )
    return SearchCheck(first, len(QUESTIONS))


def _unit(vectors: list[list[float]]) -> np.ndarray:
    array = np.asarray(vectors, dtype=np.float64)
    norms = np.linalg.norm(array, axis=1, keepdims=True)
    return array / np.where(norms == 0, 1, norms)
