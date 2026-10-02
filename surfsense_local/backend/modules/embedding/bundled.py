"""bge-small, the embedder the app ships: the default, and never deletable.

Pinned by revision and hash because every existing library was built with this
exact file. A different build of the same model is a different vector space.
"""

from pathlib import Path

from modules.embedding.spec import (
    EmbedderSpec,
    Identified,
    PinnedFile,
    Pooling,
    Source,
)
from shared.config import get_storage_settings

BGE = EmbedderSpec(
    id="bge-small-en-v1.5",
    source=Source.CURATED,
    identified=Identified.MEASURED,
    repo="Qdrant/bge-small-en-v1.5-onnx-Q",
    # A commit and checksums, public by nature: not secrets.
    # pragma: allowlist nextline secret
    revision="aa8f8b060edb00e03bfdd08813a2949946c8ba55",
    weights=PinnedFile(
        path="model_optimized.onnx",
        # pragma: allowlist nextline secret
        sha256="51f1bd0addd6e859e42c2c8021a5e5461385bb676a649f4b269aa445449f2431",
    ),
    tokenizer=PinnedFile(
        path="tokenizer.json",
        # pragma: allowlist nextline secret
        sha256="d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66",
    ),
    dimension=384,
    pooling=Pooling.CLS,
    normalize=True,
    max_tokens=512,
    # How much of the order meaning owns. The eval corpus is flat across 0.6 to
    # 0.65 for bge and falls away either side: the middle of a measured plateau,
    # not a default. Reciprocal rank fusion was tried first and rejected at 88%
    # of answers in the top 5, against 98% here.
    semantic_weight=0.65,
)


def bundled_dir() -> Path:
    return get_storage_settings().models_dir / BGE.id
