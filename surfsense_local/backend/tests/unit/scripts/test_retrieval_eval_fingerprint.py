"""The key that decides whether a built index can be reused."""

import pytest
from retrieval_eval.fingerprint import fingerprint

pytestmark = pytest.mark.unit

TOKENIZER = "unicode61"


def _corpus(directory, **files):
    directory.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (directory / f"{name}.md").write_text(text, encoding="utf-8")
    return directory


def test_the_same_corpus_and_embedder_reuse_one_index(tmp_path) -> None:
    """Re-running an unchanged eval must not pay to embed it again."""
    corpus = _corpus(tmp_path / "a", manual="warranty is 27 months")

    assert fingerprint(corpus, embedder=b"embedder-1", tokenizer=TOKENIZER) == (
        fingerprint(corpus, embedder=b"embedder-1", tokenizer=TOKENIZER)
    )


def test_an_edited_document_builds_a_new_index(tmp_path) -> None:
    """A corpus change must not be scored against the old index."""
    before = _corpus(tmp_path / "before", manual="warranty is 27 months")
    after = _corpus(tmp_path / "after", manual="warranty is 39 months")

    assert fingerprint(before, embedder=b"same", tokenizer=TOKENIZER) != (
        fingerprint(after, embedder=b"same", tokenizer=TOKENIZER)
    )


def test_an_added_document_builds_a_new_index(tmp_path) -> None:
    """A new document is a new set of distractors, so old scores do not carry."""
    one = _corpus(tmp_path / "one", manual="warranty is 27 months")
    two = _corpus(
        tmp_path / "two", manual="warranty is 27 months", policy="returns run 45 days"
    )

    assert fingerprint(one, embedder=b"same", tokenizer=TOKENIZER) != (
        fingerprint(two, embedder=b"same", tokenizer=TOKENIZER)
    )


def test_a_different_embedder_builds_a_new_index(tmp_path) -> None:
    """Vectors from another model are unrelated numbers, not a smaller change."""
    corpus = _corpus(tmp_path / "c", manual="warranty is 27 months")

    assert fingerprint(corpus, embedder=b"embedder-1", tokenizer=TOKENIZER) != (
        fingerprint(corpus, embedder=b"embedder-2", tokenizer=TOKENIZER)
    )


def test_a_different_tokenizer_builds_a_new_index(tmp_path) -> None:
    """The keyword leg reads terms, so the rule that made them is what was indexed.

    Left out of the key, a tokenizer change scores against an index built under
    the old rule and reports the old rule's numbers as the new one's.
    """
    corpus = _corpus(tmp_path / "c", manual="warranty is 27 months")

    assert fingerprint(corpus, embedder=b"same", tokenizer="unicode61") != fingerprint(
        corpus, embedder=b"same", tokenizer="unicode61 categories 'L* N* Co M*'"
    )
