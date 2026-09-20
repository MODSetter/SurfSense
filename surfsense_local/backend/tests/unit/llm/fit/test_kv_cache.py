"""The KV term, checked against llama.cpp's own allocation log.

Expected values are what `llama_kv_cache: size = ...` printed at b11050, not a
re-derivation of the formula under test.
"""

import pytest

from modules.llm.fit import KvPrecision, ModelShape, kv_cache_bytes

pytestmark = pytest.mark.unit

MIB = 1024**2

# Qwen3 1.7B: 28 blocks, 8 kv heads, 128 key/value. Measured on an M2 at b11050.
QWEN3_1_7B = ModelShape(
    architecture="qwen3",
    block_count=28,
    head_count_kv=8,
    key_length=128,
    value_length=128,
    context_length=40960,
    n_vocab=151936,
)


def test_the_window_is_priced_as_llama_cpp_allocates_it() -> None:
    """`llama_kv_cache: size = 1792.00 MiB (16384 cells, 28 layers)`, measured."""
    assert kv_cache_bytes(QWEN3_1_7B, 16384, KvPrecision.F16) == 1792 * MIB


def test_a_wider_window_costs_proportionally_more() -> None:
    """Same model at 40960 cells reported 4480.00 MiB, measured in the same run."""
    assert kv_cache_bytes(QWEN3_1_7B, 40960, KvPrecision.F16) == 4480 * MIB


def test_quantizing_the_cache_roughly_halves_it() -> None:
    """GGUF's block_q8_0 is 32 int8 weights plus one fp16 scale, so 34 bytes buys
    what f16 spends 64 on. 1792 MiB * 34/64 = 952 MiB.

    This is the swing that converts a spill into residency on a small card, which
    is why precision is an output of the fit calculation rather than a default.
    """
    assert kv_cache_bytes(QWEN3_1_7B, 16384, KvPrecision.Q8_0) == 952 * MIB
