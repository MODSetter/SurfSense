"""Turn a parsed header into the estimator's inputs.

Architecture-scoped keys are named after the architecture itself, so every
lookup goes through the `general.architecture` value rather than a fixed prefix.
The key names come from llama.cpp's own `Keys` table rather than from string
literals here, so a rename upstream is an import error rather than a field that
silently reads zero.
"""

from typing import Any

from gguf.constants import Keys

from modules.llm.fit import ModelShape
from modules.llm.gguf.header_prefix import GgufHeader, read_header_prefix

_LLM = Keys.LLM
_ATTENTION = Keys.Attention


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
    arch = str(meta.get(Keys.General.ARCHITECTURE, "unknown"))

    def field(key: str, default: int = 0) -> int:
        return _widest(meta.get(key.format(arch=arch)), default)

    key_length = field(_ATTENTION.KEY_LENGTH)
    value_length = field(_ATTENTION.VALUE_LENGTH)
    embedding = field(_LLM.EMBEDDING_LENGTH)
    head_count = field(_ATTENTION.HEAD_COUNT)
    # Older headers omit the per-head lengths and imply them from the embedding.
    if not key_length and embedding and head_count:
        key_length = value_length = embedding // head_count

    period, layers = _sliding_pattern(meta.get(_ATTENTION.SLIDING_WINDOW_PATTERN.format(arch=arch)))

    tokens = meta.get(Keys.Tokenizer.LIST)
    return ModelShape(
        architecture=arch,
        block_count=field(_LLM.BLOCK_COUNT),
        head_count_kv=field(_ATTENTION.HEAD_COUNT_KV, 1),
        key_length=key_length,
        value_length=value_length,
        context_length=field(_LLM.CONTEXT_LENGTH),
        n_vocab=len(tokens) if isinstance(tokens, list) else field(_LLM.VOCAB_SIZE),
        sliding_window=field(_ATTENTION.SLIDING_WINDOW),
        expert_count=field(_LLM.EXPERT_COUNT),
        embedding_length=embedding,
        feed_forward_length=field(_LLM.FEED_FORWARD_LENGTH),
        expert_feed_forward_length=field(_LLM.EXPERT_FEED_FORWARD_LENGTH),
        expert_shared_feed_forward_length=field(_LLM.EXPERT_SHARED_FEED_FORWARD_LENGTH),
        expert_used_count=field(_LLM.EXPERT_USED_COUNT),
        sliding_window_pattern=period,
        sliding_window_layers=layers,
        shared_kv_layers=field(_ATTENTION.SHARED_KV_LAYERS),
        kv_lora_rank=field(_ATTENTION.KV_LORA_RANK),
        key_length_mla=field(_ATTENTION.KEY_LENGTH_MLA),
    )


def _sliding_pattern(value: Any) -> tuple[int, tuple[bool, ...]]:
    """The window pattern in whichever of its two forms the header used.

    llama.cpp accepts both: one integer meaning "every nth layer sees the whole
    window", or one flag per layer. A file that states either is the authority,
    so the caller prefers this over any table.
    """
    if isinstance(value, list):
        return 0, tuple(bool(v) for v in value)
    if value is None:
        return 0, ()
    return int(value), ()


def read_header(data: bytes) -> ModelShape:
    """Bytes from the front of a GGUF file to the shape a fit estimate needs."""
    return to_shape(read_header_prefix(data))
