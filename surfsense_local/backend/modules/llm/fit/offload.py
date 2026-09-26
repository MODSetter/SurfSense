"""How much of a model ends up on the processor when it does not all fit.

llama.cpp does not split a model by bytes. Its fitter fills devices with whole
layers, back to front, and stops at the last one that fits, so the answer is a
count of layers over the layer count rather than a ratio of bytes.

Measured on an RTX 3050, Qwen3 4B spilled 602 MiB of weights plus 320 MiB of
cache: 0.19 of the model. The byte ratio said 0.12. Both agree on the verdict
and on the ordering, but the fraction is what grades the reason line and gates
the recommendation, so it is the fraction that has to be right.

Only layers move. The projector is pinned by a flag rather than placed by the
fitter, and the compute buffer belongs to whichever device runs the graph, so
neither is part of what a layer costs.
"""

from math import ceil

from modules.llm.fit.itemisation import NeedItems
from modules.llm.fit.types import ModelShape


def offload_fraction(shape: ModelShape, items: NeedItems, resident_bytes: int) -> float:
    """Fraction of the model's layers that will not fit on the device.

    Returns 0.0 when everything fits, and never more than 1.0.
    """
    spilled = items.total - resident_bytes
    if spilled <= 0:
        return 0.0
    if shape.block_count <= 0:
        return min(1.0, spilled / items.total) if items.total else 1.0

    movable = items.weights_bytes + items.kv_bytes
    per_layer = movable / shape.block_count
    if per_layer <= 0:
        return 1.0

    layers_out = ceil(spilled / per_layer)
    return min(1.0, layers_out / shape.block_count)
