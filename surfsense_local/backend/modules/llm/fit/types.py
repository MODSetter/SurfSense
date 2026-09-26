"""What the estimator reasons over: a model's shape and a machine's memory."""

from dataclasses import dataclass
from enum import StrEnum


class KvPrecision(StrEnum):
    """How the conversation cache is stored.

    The load plan chooses between `F16` and `Q8_0`, and the preset writes only
    those two: lossless either way, but a quantized cache needs a working flash
    attention kernel and f16 does not. The others exist because a searched
    model's header can name any of them and they have to be priceable.
    """

    F32 = "f32"
    F16 = "f16"
    BF16 = "bf16"
    Q8_0 = "q8_0"
    Q5_1 = "q5_1"
    Q5_0 = "q5_0"
    Q4_1 = "q4_1"
    Q4_0 = "q4_0"
    IQ4_NL = "iq4_nl"

    @property
    def bytes_per_element(self) -> float:
        """Cost per cached element, from the block layout table."""
        from modules.llm.fit.cache_types import BYTES_PER_ELEMENT

        return BYTES_PER_ELEMENT[self]


@dataclass(frozen=True)
class ModelShape:
    """Estimator inputs, named after the GGUF metadata keys they come from.

    Quantization-independent: measured, the architecture fields are identical
    across Q4_K_M, Q8_0 and f16 of the same model, so one header read prices
    every build of it.
    """

    architecture: str
    block_count: int
    head_count_kv: int
    key_length: int
    value_length: int
    context_length: int
    n_vocab: int
    sliding_window: int = 0
    expert_count: int = 0

    # Everything below is optional so an older header, or a synthetic shape in a
    # test, still constructs. Each one only ever makes an estimate sharper, and
    # its absence is the conservative answer rather than a zero cost.

    # Graph scratch scales with the widest thing a layer computes, not with the
    # model's parameter count.
    embedding_length: int = 0
    feed_forward_length: int = 0
    expert_feed_forward_length: int = 0
    expert_shared_feed_forward_length: int = 0
    expert_used_count: int = 0

    # Which layers hold the whole window. The header states this directly on
    # newer files, as a period or as one flag per layer, and llama.cpp reads it
    # before falling back to a per architecture default.
    sliding_window_pattern: int = 0
    sliding_window_layers: tuple[bool, ...] = ()

    # What a sliding layer caches, where that is narrower than what a full
    # attention layer caches. llama.cpp selects between the two per layer, so a
    # model stating both is charged each layer at its own width. Zero means the
    # header states no separate width and every layer is priced at
    # `key_length` / `value_length`.
    key_length_swa: int = 0
    value_length_swa: int = 0

    # Heads per layer, where a model does not carry the same number on each.
    # `head_count_kv` is the widest of them, kept for callers that want one
    # number; the cache is a sum over layers and reads this instead. Pricing
    # every layer at the widest over-states a model whose layers differ by
    # however far apart they are.
    head_count_kv_layers: tuple[int, ...] = ()
    # Layers that reuse an earlier layer's cache and so allocate none of their own.
    shared_kv_layers: int = 0

    # Multi-head latent attention: one compressed entry per token per layer
    # instead of a key and a value per head.
    kv_lora_rank: int = 0
    key_length_mla: int = 0
