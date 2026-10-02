"""A Hugging Face embedder's spec, read from the files its repo ships."""

import pytest

from modules.embedding.huggingface.pick import PickedFiles
from modules.embedding.huggingface.spec_from_repo import RepoConfig, spec_from_repo
from modules.embedding.spec import Identified, Pooling, Source
from modules.llm.catalog.local.listed_file import ListedFile

pytestmark = pytest.mark.unit

REV = "b" * 40
PICKED = PickedFiles(
    ListedFile("onnx/model_int8.onnx", 120_000_000, "1" * 64),
    (),
    ListedFile("tokenizer.json", 17_000_000, "2" * 64),
)
E5 = RepoConfig(
    config={"hidden_size": 384, "max_position_embeddings": 512},
    pooling={"pooling_mode_mean_tokens": True},
    modules=[{"type": "sentence_transformers.models.Normalize"}],
    prompts={"query": "query: ", "passage": "passage: "},
    max_seq_length=512,
)


def test_an_asymmetric_model_keeps_its_prompts_and_pooling() -> None:
    """multilingual-e5 embeds questions and passages with their own prefixes."""
    spec = spec_from_repo(
        "intfloat/multilingual-e5-small", REV, PICKED, E5, "sentence-similarity"
    )

    assert spec.source is Source.HUGGINGFACE
    assert spec.identified is Identified.DECLARED
    assert (spec.query_prefix, spec.document_prefix) == ("query: ", "passage: ")
    assert spec.pooling is Pooling.MEAN
    assert spec.dimension == 384
    assert spec.max_tokens == 512
    assert spec.weights.path == "model_int8.onnx"
    assert spec.semantic_weight == 0.65


def test_a_repo_with_no_sentence_transformers_files_is_inferred() -> None:
    """Only the pipeline tag says it embeds; the rest takes bge's defaults."""
    bare = RepoConfig(
        config={"hidden_size": 768},
        pooling=None,
        modules=None,
        prompts=None,
        max_seq_length=None,
    )

    spec = spec_from_repo("someone/embedder", REV, PICKED, bare, "feature-extraction")

    assert spec.identified is Identified.INFERRED
    assert spec.pooling is Pooling.CLS
    assert spec.dimension == 768
    assert spec.max_tokens == 512


def test_last_token_pooling_is_read() -> None:
    """Decoder embedders pool on their last token and prompt their queries."""
    qwen = RepoConfig(
        config={"hidden_size": 1024},
        pooling={"pooling_mode_lasttoken": True},
        modules=[],
        prompts={"query": "Instruct: retrieve\nQuery: ", "document": ""},
        max_seq_length=8192,
    )

    spec = spec_from_repo(
        "Qwen/Qwen3-Embedding-0.6B", REV, PICKED, qwen, "feature-extraction"
    )

    assert spec.pooling is Pooling.LAST
    assert spec.query_prefix.startswith("Instruct:")
    # Passages are cut at 480 of bge's tokens; another tokenizer may count more,
    # never four times as many, and a longer window only costs memory.
    assert spec.max_tokens == 2048
