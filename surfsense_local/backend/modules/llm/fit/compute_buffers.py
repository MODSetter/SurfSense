"""The scratch memory a graph needs beyond weights and cache.

Absent from earlier drafts of the estimator entirely, which under-stated `need`
by enough to flip a verdict on a 6 GB card.

> ponytail: two measured points, one model, one backend. Qwen3 1.7B on Metal at
> b11050 reported 102.24 MiB at 16384 and 222.24 MiB at 40960, and a 4B on
> Vulkan reported 143.62 device plus 26.01 host at 16384. The line below passes
> through the Metal pair and is the best available answer, not a law. Replace it
> with the machine's own residual after the first load, which measures this term
> along with everything else that is neither weights nor cache.
"""

_BASE_BYTES = 23 * 1024**2
_PER_TOKEN_BYTES = 5_120


def compute_buffer_bytes(n_ctx: int) -> int:
    """Scratch bytes for a graph over an `n_ctx` window, rounded up.

    Rounding up is the rule the whole estimator runs on: over-stating costs a
    pessimistic badge, under-stating ships a confident badge about a model that
    spills.
    """
    return _BASE_BYTES + _PER_TOKEN_BYTES * n_ctx
