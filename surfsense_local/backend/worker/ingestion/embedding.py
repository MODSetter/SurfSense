from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from shared.config import get_search_settings, get_storage_settings

# int8 ONNX bge-small-en-v1.5: 384 dims, CLS pooling. Fetched by fetch_embedding_model.py.
EMBEDDING_REPO = "Qdrant/bge-small-en-v1.5-onnx-Q"
EMBEDDING_FILES = ["model_optimized.onnx", "tokenizer.json", "config.json"]
MODEL_DIR_NAME = "bge-small-en-v1.5"

MAX_TOKENS = 512
BATCH = 32


def embedding_dir() -> Path:
    return get_storage_settings().models_dir / MODEL_DIR_NAME


def missing_embedding_files() -> list[str]:
    """Files a development install still needs before retrieval can run."""
    directory = embedding_dir()
    return [name for name in EMBEDDING_FILES if not (directory / name).is_file()]


@lru_cache(maxsize=1)
def tokenizer() -> Any:
    """The clean tokenizer, shared with the chunker for token counting."""
    from tokenizers import Tokenizer

    return Tokenizer.from_file(str(embedding_dir() / "tokenizer.json"))


@lru_cache(maxsize=1)
def _encoder() -> Any:
    from tokenizers import Tokenizer

    encoder = Tokenizer.from_file(str(embedding_dir() / "tokenizer.json"))
    encoder.enable_truncation(max_length=MAX_TOKENS)
    encoder.enable_padding()
    return encoder


@lru_cache(maxsize=1)
def _session() -> Any:
    import onnxruntime as ort

    return ort.InferenceSession(
        str(embedding_dir() / "model_optimized.onnx"),
        providers=["CPUExecutionProvider"],
    )


def embed(texts: list[str]) -> list[list[float]]:
    """Embed every text with the bundled model, in batches, on this CPU."""
    width = get_search_settings().embedding_dimension
    vectors: list[list[float]] = []

    for start in range(0, len(texts), BATCH):
        vectors.extend(_embed_batch(texts[start : start + BATCH]))

    wrong = next((len(v) for v in vectors if len(v) != width), None)
    if wrong is not None:
        raise ValueError(
            f"{MODEL_DIR_NAME} returned {wrong} dimensions, and the index was "
            f"built for {width}"
        )

    return vectors


def _embed_batch(texts: list[str]) -> list[list[float]]:
    encoded = _encoder().encode_batch(texts)
    feed = {
        "input_ids": np.array([e.ids for e in encoded], dtype=np.int64),
        "attention_mask": np.array([e.attention_mask for e in encoded], dtype=np.int64),
    }
    # Some int8 exports drop token_type_ids; feed it only if the graph asks.
    session = _session()
    if any(i.name == "token_type_ids" for i in session.get_inputs()):
        feed["token_type_ids"] = np.array([e.type_ids for e in encoded], dtype=np.int64)

    last_hidden = session.run(None, feed)[0]
    # bge pools on the CLS token, not the mean, then normalises to unit length.
    cls = last_hidden[:, 0]
    normalised = cls / np.linalg.norm(cls, axis=1, keepdims=True)
    return normalised.astype(np.float32).tolist()
