"""One pool, on a machine where the GPU and the CPU share the same chips.

Apple Silicon reports two views of one memory, and adding them is the mistake
this module exists to prevent: Metal states `recommendedMaxWorkingSetSize` as
both its total and its free, while the host states the same physical memory
again. Summed, an 8 GB Mac priced as though it had 10.3 GB.

Two limits apply and the smaller governs. The working set is a ceiling Metal
will not allocate past, and it is exactly the figure llama.cpp's fitter
subtracts its own margin from, so discounting it again would refuse a model the
runtime demonstrably places. Host memory is what is actually there, and that is
the leg that lies: it is a snapshot, and loading weights takes seconds during
which another application can take memory.

Measured: spending the working set as though it were live sized a 28,672 token
window on an 8 GB Mac with 2.3 GB reclaimable. The load paged and took 43
seconds, long enough for title generation to time out at 30.
"""

# What the pool leaves to the rest of the machine. Not a margin for the model,
# which llama.cpp's own fit reserve already covers, but for the seconds between
# reading this number and finishing the load.
UMA_HOST_FRACTION = 0.85


def unified_pool_bytes(working_set_bytes: int, host_bytes: int) -> int:
    """What a unified memory machine can actually give a model."""
    return min(working_set_bytes, int(UMA_HOST_FRACTION * host_bytes))
