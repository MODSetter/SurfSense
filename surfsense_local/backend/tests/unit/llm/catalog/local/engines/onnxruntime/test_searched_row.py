"""An opened Hugging Face repo with no build to offer: the row says why."""

import pytest

from modules.embedding.huggingface.pick import NotAnEmbedderCode
from modules.llm.catalog.local.engines.onnxruntime.rows import searched_row

pytestmark = pytest.mark.unit

REPO = "sentence-transformers/all-MiniLM-L6-v2"


def test_the_check_s_sentence_travels_with_its_own_code() -> None:
    """The check words its refusal itself and names it. The embedding group's
    code would put that group's sentence on screen in its place."""
    row = searched_row(
        REPO, None, "This repo has no tokenizer.json.", NotAnEmbedderCode.NO_TOKENIZER
    )

    assert not row.runnable
    assert row.not_runnable_reason == "This repo has no tokenizer.json."
    assert row.not_runnable_code == "repo_no_tokenizer"


def test_a_sentence_with_no_code_travels_without_one() -> None:
    """The one that names a file. The interface shows it as it came."""
    sentence = "Hugging Face lists no checksum for onnx/model.onnx."
    row = searched_row(REPO, None, sentence)

    assert not row.runnable
    assert row.not_runnable_reason == sentence
    assert row.not_runnable_code is None


def test_a_refusal_with_no_sentence_falls_back_to_the_plain_one_and_its_code() -> None:
    """A refusal with no sentence falls back to the plain one and its code."""
    row = searched_row(REPO, None, None)

    assert not row.runnable
    assert row.not_runnable_reason == "SurfSense cannot run this model."
    assert row.not_runnable_code == "unsupported"


def test_a_code_without_its_sentence_is_dropped() -> None:
    """The fallback sentence must not travel under another refusal's code."""
    row = searched_row(REPO, None, None, NotAnEmbedderCode.NO_ONNX)

    assert row.not_runnable_reason == "SurfSense cannot run this model."
    assert row.not_runnable_code == "unsupported"
