"""Turn a parsed header into the estimator's inputs.

Architecture-scoped keys are named after the architecture itself, so every
lookup goes through the `general.architecture` value rather than a fixed prefix.
"""

from typing import Any

from modules.llm.fit import ModelShape
from modules.llm.gguf.reader import GgufHeader, read_gguf_header


def _widest(value: Any, default: int = 0) -> int:
    """A field that is scalar in most models and per-layer in some.

    The widest layer is the honest reduction: it is what the cache must be sized
    for, and taking the first element instead under-prices a hybrid model.
    """
    if isinstance(value, list):
        return max((int(v) for v in value), default=default)
    if value is None:
        return default
    return int(value)


def to_shape(header: GgufHeader) -> ModelShape:
    meta = header.metadata
    arch = str(meta.get("general.architecture", "unknown"))

    def field(name: str, default: int = 0) -> int:
        return _widest(meta.get(f"{arch}.{name}"), default)

    key_length = field("attention.key_length")
    value_length = field("attention.value_length")
    embedding = field("embedding_length")
    head_count = field("attention.head_count")
    # Older headers omit the per-head lengths and imply them from the embedding.
    if not key_length and embedding and head_count:
        key_length = value_length = embedding // head_count

    tokens = meta.get("tokenizer.ggml.tokens")
    return ModelShape(
        architecture=arch,
        block_count=field("block_count"),
        head_count_kv=field("attention.head_count_kv", 1),
        key_length=key_length,
        value_length=value_length,
        context_length=field("context_length"),
        n_vocab=len(tokens) if isinstance(tokens, list) else field("vocab_size"),
        sliding_window=field("attention.sliding_window"),
        expert_count=field("expert_count"),
    )


def read_header(data: bytes) -> ModelShape:
    """Bytes from the front of a GGUF file to the shape a fit estimate needs."""
    return to_shape(read_gguf_header(data))
