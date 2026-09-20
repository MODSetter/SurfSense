"""The conversation cache's memory cost, which is architecture-derived and
independent of how the weights were quantized."""

from modules.llm.fit.sliding_window import global_layer_count
from modules.llm.fit.types import KvPrecision, ModelShape


def kv_cache_bytes(shape: ModelShape, n_ctx: int, precision: KvPrecision) -> int:
    """Bytes the KV cache occupies for a window of `n_ctx` tokens.

    One key and one value per attention head per layer per token. Verified exact
    against llama.cpp's own allocation on two backends.

    A model with sliding-window attention holds the full context on only some of
    its layers, but the header does not say which, so an architecture we cannot
    name is priced as though every layer were global. That over-states memory,
    which is the only direction it is safe to be wrong in.
    """
    bytes_per_layer_token = int(
        shape.head_count_kv
        * (shape.key_length + shape.value_length)
        * precision.bytes_per_element
    )

    if shape.sliding_window <= 0 or shape.sliding_window >= n_ctx:
        return bytes_per_layer_token * shape.block_count * n_ctx

    globals_ = global_layer_count(shape.architecture, shape.block_count)
    if globals_ is None:
        return bytes_per_layer_token * shape.block_count * n_ctx

    locals_ = shape.block_count - globals_
    return bytes_per_layer_token * (globals_ * n_ctx + locals_ * shape.sliding_window)
