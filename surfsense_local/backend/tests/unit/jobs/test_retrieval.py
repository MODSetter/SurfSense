"""Which passages a question is shown: all of them when they fit, else its best few, found by
the document's title as well as by the passage's own words."""

import pytest

from modules.jobs.evidence.passages import SourceText, passages_of
from modules.jobs.evidence.retrieval import Retriever

pytestmark = pytest.mark.unit

FILLER = "\n\n".join(
    f"## Note {n}\n\nRoutine text about meetings number {n}." for n in range(40)
)
SOURCES = [
    SourceText(
        1,
        "access-management-policy",
        "## Policy\n\nRequests are approved before any change.",
    ),
    SourceText(2, "meeting-notes", FILLER),
]


def test_every_passage_is_shown_when_they_fit():
    """Within the budget nothing is left out, in the order the sources wrote it."""
    passages = passages_of(SOURCES)
    retriever = Retriever(passages, budget_chars=1_000_000, per_question=2)

    assert retriever.whole
    assert retriever.for_question("anything") == list(range(len(passages)))


def test_a_passage_is_found_by_its_documents_title():
    """A policy's own name counts: "access management" finds the access management policy's passage."""
    passages = passages_of(SOURCES)
    retriever = Retriever(passages, budget_chars=100, per_question=2)

    shown = retriever.for_question("Are access management policies established?")

    assert not retriever.whole
    assert passages[shown[0]].title == "access-management-policy"


def test_a_standing_query_shows_its_passages_with_every_question():
    """How the firm reviews its policies reaches a question that never says "review"."""
    sources = [
        *SOURCES,
        SourceText(
            3, "policy-management", "## Review\n\nPolicies are reviewed yearly."
        ),
    ]
    passages = passages_of(sources)
    retriever = Retriever(
        passages,
        budget_chars=100,
        per_question=1,
        standing=("policies reviewed yearly",),
        per_standing=1,
    )

    shown = [passages[i].title for i in retriever.for_question("Is access approved?")]

    assert shown == ["access-management-policy", "policy-management"]


def test_with_an_embedder_meaning_takes_turns_with_the_words():
    """A passage no word of the question names is shown when the embedder finds it close."""
    sources = [
        *SOURCES,
        SourceText(3, "vendors", "## Vendors\n\nSuppliers are vetted."),
    ]
    passages = passages_of(sources)
    vendors = next(i for i, p in enumerate(passages) if p.title == "vendors")

    def embed(texts, query):
        # The question and the vendors passage point one way, everything else another.
        return [
            [1.0, 0.0] if query or "Suppliers" in text else [0.0, 1.0] for text in texts
        ]

    words_only = Retriever(passages, budget_chars=100, per_question=2)
    with_meaning = Retriever(passages, budget_chars=100, per_question=2, embed=embed)
    question = "Is supply chain risk managed for the access management policy?"

    assert vendors not in words_only.for_question(question)
    assert vendors in with_meaning.for_question(question)
