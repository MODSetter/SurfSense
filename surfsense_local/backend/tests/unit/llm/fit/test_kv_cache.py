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


def test_cells_are_padded_the_way_the_allocator_pads_them() -> None:
    """llama.cpp aligns the cache to 256 cells, so a window one token past a
    boundary costs a whole block more. Pricing the raw token count under-states
    every window that is not already aligned."""
    aligned = kv_cache_bytes(QWEN3_1_7B, 16384, KvPrecision.F16)
    one_past = kv_cache_bytes(QWEN3_1_7B, 16385, KvPrecision.F16)

    assert one_past == kv_cache_bytes(QWEN3_1_7B, 16640, KvPrecision.F16)
    assert one_past > aligned


def test_a_latent_attention_model_caches_one_compressed_entry_per_token() -> None:
    """DeepSeek-class models cache a latent, not a key and a value per head, and
    such a header reports one KV head while the model runs many.

    Priced by the ordinary formula this reads far too small, because it would
    take that single head at face value. The latent's own width is what governs.
    """
    deepseek_like = ModelShape(
        architecture="deepseek2",
        block_count=28,
        head_count_kv=1,
        key_length=192,
        value_length=128,
        context_length=163840,
        n_vocab=129280,
        kv_lora_rank=512,
        key_length_mla=64,
    )

    per_layer_token = (512 + 64) * 2
    expected = per_layer_token * 28 * 16384

    assert kv_cache_bytes(deepseek_like, 16384, KvPrecision.F16) == expected


# Gemma 4 12B, read from the real header. Two things make it heterogeneous, and
# both are per layer: the sliding layers carry 8 KV heads at 256 wide, while the
# full-attention layers carry 1 head at 512. Measured on an M2 and an RTX 3050
# at b11050, identical on both.
GEMMA4_12B = ModelShape(
    architecture="gemma4",
    block_count=48,
    head_count_kv=8,
    head_count_kv_layers=tuple((8, 8, 8, 8, 8, 1)[index % 6] for index in range(48)),
    key_length=512,
    value_length=512,
    key_length_swa=256,
    value_length_swa=256,
    context_length=262144,
    n_vocab=262144,
    sliding_window=1024,
    sliding_window_layers=tuple(
        (True, True, True, True, True, False)[index % 6] for index in range(48)
    ),
)


@pytest.mark.parametrize(
    ("n_ctx", "measured_mib"),
    [(4096, 544), (8192, 608), (16384, 736), (32768, 992)],
)
def test_a_layer_keeps_its_own_head_count_and_width(n_ctx, measured_mib) -> None:
    """llama.cpp sizes each layer from `n_embd_k_gqa(il)`, which reads that
    layer's own head count and its own key width.

    Collapsing either to one number per model prices all 48 layers as though
    they were the widest of them, which over-stated this model by 5.1x at 32768:
    5056 MiB against the 992 llama.cpp allocates.
    """
    assert kv_cache_bytes(GEMMA4_12B, n_ctx, KvPrecision.F16) == measured_mib * MIB
