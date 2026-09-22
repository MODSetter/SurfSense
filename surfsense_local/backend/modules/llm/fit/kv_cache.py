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

    A sum over layers rather than one layer's cost times a count, because
    llama.cpp sizes each layer from its own `n_embd_k_gqa(il)`: that layer's
    head count times that layer's key width, both of which a header may state
    per layer. Reducing either to one number and multiplying prices every layer
    as though it were the widest, which on a model whose layers differ was
    measured five times over what the runtime allocates.

    Verified exact against llama.cpp's own allocation on two backends.
    """
    caching = _caching_layers(shape)
    if caching <= 0:
        return 0

    # None where no pattern can be had, which prices every layer at full width:
    # over-stating memory is the only direction it is safe to be wrong in.
    sliding = sliding_layers(shape) if shape.sliding_window > 0 else None
    full_cells = global_cells(n_ctx)
    local = local_cells(shape.sliding_window, n_ctx) if sliding else full_cells

    # The header's pattern describes the model's layers; the ones that cache are
    # a prefix of those, since shared layers reuse an earlier layer's cache.
    total = 0
    for index in range(caching):
        slides = sliding is not None and sliding[index]
        total += _bytes_per_layer_token(shape, precision, index, slides=slides) * (
            local if slides else full_cells
        )
    return total


def _bytes_per_layer_token(
    shape: ModelShape, precision: KvPrecision, index: int, *, slides: bool
) -> int:
    """One layer's cache entry for one token.

    A sliding layer is charged its own width where the model states one, which
    is what `n_embd_head_k(il)` selects between. Absent that, both kinds of
    layer are the same width and the distinction costs nothing.
    """
    if is_latent(shape):
        return latent_bytes_per_layer_token(shape, precision)
    key = shape.key_length_swa if slides and shape.key_length_swa else shape.key_length
    value = (
        shape.value_length_swa
        if slides and shape.value_length_swa
        else shape.value_length
    )
    return int(_head_count(shape, index) * (key + value) * precision.bytes_per_element)


def _head_count(shape: ModelShape, index: int) -> int:
    """KV heads on one layer.

    The scalar is the widest layer's count, which is the right answer only for a
    model that carries the same number on each. Where the header lists them, the
    list is what llama.cpp reads.
    """
    if not shape.head_count_kv_layers:
        return shape.head_count_kv
    return shape.head_count_kv_layers[index % len(shape.head_count_kv_layers)]


def _caching_layers(shape: ModelShape) -> int:
    """Layers that allocate a cache of their own.

    Gemma 3n and Gemma 4 reuse an earlier layer's cache on their last blocks, so
    charging those layers a cache each over-states the window's cost on exactly
    the models chosen to be cheap on a small machine.
    """
    return max(0, shape.block_count - shape.shared_kv_layers)
