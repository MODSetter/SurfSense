"""The conversation cache's memory cost.

Architecture-derived and independent of how the weights were quantized, which is
what lets one header read price every build of a model.

Three things decide it, and each has its own module: how wide one layer's entry
is (here, or `mla_cache` for a latent model), how many cells a layer allocates
(`kv_cells`), and which layers hold the whole window rather than a slice
(`sliding_window`).
"""

from modules.llm.fit.kv_cells import global_cells, local_cells
from modules.llm.fit.mla_cache import is_latent, latent_bytes_per_layer_token
from modules.llm.fit.sliding_window import sliding_layers
from modules.llm.fit.types import KvPrecision, ModelShape


def kv_cache_bytes(shape: ModelShape, n_ctx: int, precision: KvPrecision) -> int:
    """Bytes the KV cache occupies for a window of `n_ctx` tokens.

    Verified exact against llama.cpp's own allocation on two backends.
    """
    per_layer_token = _bytes_per_layer_token(shape, precision)
    caching = _caching_layers(shape)
    if caching <= 0 or per_layer_token <= 0:
        return 0

    window = shape.sliding_window
    if window <= 0:
        return per_layer_token * caching * global_cells(n_ctx)

    sliding = sliding_layers(shape)
    if sliding is None:
        # No pattern to be had, so every layer is priced at full width.
        return per_layer_token * caching * global_cells(n_ctx)

    # The header's pattern describes the model's layers; the ones that cache are
    # a prefix of those, since shared layers reuse an earlier layer's cache.
    local = sum(1 for slides in sliding[:caching] if slides)
    full = caching - local
    return per_layer_token * (
        full * global_cells(n_ctx) + local * local_cells(window, n_ctx)
    )


def _bytes_per_layer_token(shape: ModelShape, precision: KvPrecision) -> int:
    """One layer's cache entry for one token."""
    if is_latent(shape):
        return latent_bytes_per_layer_token(shape, precision)
    return int(
        shape.head_count_kv
        * (shape.key_length + shape.value_length)
        * precision.bytes_per_element
    )


def _caching_layers(shape: ModelShape) -> int:
    """Layers that allocate a cache of their own.

    Gemma 3n and Gemma 4 reuse an earlier layer's cache on their last blocks, so
    charging those layers a cache each over-states the window's cost on exactly
    the models chosen to be cheap on a small machine.
    """
    return max(0, shape.block_count - shape.shared_kv_layers)
