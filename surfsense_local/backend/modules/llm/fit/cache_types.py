"""Bytes one cache element costs, per storage type.

A quantized cache stores a block of weights plus a scale, so the cost per
element is not the bit width divided by eight: `q8_0` is one byte per weight
plus one fp16 scale for every thirty two of them.

The preset only ever writes `f16` or `q8_0`, which are the two the load plan
chooses between. The rest are here because a searched model's own header can
name any of them, and one table is better than a second one written later
somewhere else.
"""

from modules.llm.fit.types import KvPrecision

# Block layouts from ggml-common.h. Each entry is bytes per element: the block's
# total size divided by the number of weights it holds.
BYTES_PER_ELEMENT: dict[KvPrecision, float] = {
    KvPrecision.F32: 4.0,
    KvPrecision.F16: 2.0,
    KvPrecision.BF16: 2.0,
    KvPrecision.Q8_0: 34 / 32,  # 32 int8 weights plus one fp16 scale
    KvPrecision.Q5_1: 24 / 32,  # 5 bits plus an fp16 scale and an fp16 min
    KvPrecision.Q5_0: 22 / 32,  # 5 bits plus an fp16 scale
    KvPrecision.Q4_1: 20 / 32,  # 4 bits plus an fp16 scale and an fp16 min
    KvPrecision.Q4_0: 18 / 32,  # 4 bits plus an fp16 scale
    KvPrecision.IQ4_NL: 18 / 32,  # same footprint, non linear codebook
}
