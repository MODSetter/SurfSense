"""The corpus and its queries, checked against each other before a run."""

import pytest
from pydantic import ValidationError
from retrieval_eval.cases import Corpus, Document, Query, load

pytestmark = pytest.mark.unit

MANUAL = Document(
    title="manual", markdown="# Manual\n\nThe X200 is covered for 27 months."
)


def _query(**changes) -> Query:
    fields = {
        "id": "warranty",
        "slice": "english",
        "text": "How long is the warranty?",
        "expect": ["covered for 27 months"],
    }
    return Query(**{**fields, **changes})


def test_a_query_whose_answer_is_in_the_corpus_is_accepted() -> None:
    """The ordinary case: the phrase it expects is somewhere in the documents."""
    assert Corpus(documents=[MANUAL], queries=[_query()]).queries


def test_a_query_no_document_answers_is_refused() -> None:
    """A typo in `expect` would otherwise be read as retrieval failing."""
    with pytest.raises(ValidationError, match="no document contains what it expects"):
        Corpus(documents=[MANUAL], queries=[_query(expect=["covered for 72 months"])])


def test_the_shipped_corpus_answers_every_shipped_query() -> None:
    """The files in the repo, so a bad edit fails here rather than in a run."""
    corpus = load()

    assert len(corpus.documents) >= 5
    assert {query.slice for query in corpus.queries} >= {
        "english",
        "identifier",
        "superseded",
        "cross-lingual",
    }
