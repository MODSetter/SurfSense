"""The cache cost of multi-head latent attention.

DeepSeek-class models do not cache a key and a value per head. They cache one
compressed latent per token per layer, plus the rotary part of the key, and
reconstruct the rest on the way past. Priced by the ordinary formula they read
enormously too large, because such a header reports a single KV head while the
model has a hundred and more.
"""

from modules.llm.fit.types import KvPrecision, ModelShape


def is_latent(shape: ModelShape) -> bool:
    """Whether this model caches a compressed latent rather than keys and values."""
    return shape.kv_lora_rank > 0


def latent_bytes_per_layer_token(shape: ModelShape, precision: KvPrecision) -> int:
    """Bytes one layer caches per token: the latent plus the rotary key."""
    width = shape.kv_lora_rank + shape.key_length_mla
    return int(width * precision.bytes_per_element)
