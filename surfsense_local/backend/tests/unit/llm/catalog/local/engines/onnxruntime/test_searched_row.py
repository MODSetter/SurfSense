"""An opened Hugging Face repo with no build to offer: the row says why."""

import pytest

from modules.llm.catalog.local.engines.onnxruntime.rows import searched_row

pytestmark = pytest.mark.unit

REPO = "sentence-transformers/all-MiniLM-L6-v2"


def test_the_checks_own_sentence_travels_without_a_code() -> None:
    """The check words its refusal itself. The embedding group's code would put
    that group's sentence on screen in its place, so the row carries none."""
    row = searched_row(REPO, None, "This repo has no tokenizer.json.")

    assert not row.runnable
    assert row.not_runnable_reason == "This repo has no tokenizer.json."
    assert row.not_runnable_code is None


def test_a_refusal_with_no_sentence_falls_back_to_the_plain_one_and_its_code() -> None:
    """A refusal with no sentence falls back to the plain one and its code."""
    row = searched_row(REPO, None, None)

    assert not row.runnable
    assert row.not_runnable_reason == "SurfSense cannot run this model."
    assert row.not_runnable_code == "unsupported"
