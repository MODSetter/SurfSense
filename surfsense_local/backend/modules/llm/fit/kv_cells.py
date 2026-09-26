"""How many cache cells llama.cpp allocates for a window.

Not the same as the number of tokens. The cache is padded, and a sliding window
layer is sized for its window plus a micro batch rather than for the window
alone, because a batch being processed has to sit in the cache beside the window
it attends to. Both come from `llama_kv_cache_iswa`, which sizes a sliding layer
as `pad(min(size_base, n_swa * n_seq_max + n_ubatch))`.

`n_seq_max` is 1 here, pinned by the `parallel = 1` this app writes into every
preset: one user asking one question.
"""

# CUDA wants the cache aligned, and llama.cpp pads every cache to this on every
# backend rather than branching per device.
CELL_PADDING = 256

# llama-server's default micro batch. A sliding layer holds the batch being
# processed alongside the window it attends to.
UBATCH_TOKENS = 512


def pad(cells: int) -> int:
    """Round up to the alignment llama.cpp allocates on."""
    if cells <= 0:
        return 0
    return -(-cells // CELL_PADDING) * CELL_PADDING


def global_cells(n_ctx: int) -> int:
    """Cells a layer that attends to the whole conversation allocates."""
    return pad(n_ctx)


def local_cells(sliding_window: int, n_ctx: int) -> int:
    """Cells a sliding window layer allocates.

    Never more than a global layer: a window wider than the context is not a
    window at all, and llama.cpp takes the smaller of the two for that reason.
    """
    return min(global_cells(n_ctx), pad(sliding_window + UBATCH_TOKENS))
