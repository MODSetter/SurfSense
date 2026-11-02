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
