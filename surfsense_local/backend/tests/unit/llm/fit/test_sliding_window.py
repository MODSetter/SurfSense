"""Sliding-window attention: most layers hold a short window, a few hold it all.

The header declares the window size but never the pattern of which layers use
it, so the pattern is a per-architecture fact we either know or refuse to guess.
"""

import pytest

from modules.llm.fit import KvPrecision, ModelShape, kv_cache_bytes

pytestmark = pytest.mark.unit

MIB = 1024**2


def gemma_like(architecture: str) -> ModelShape:
    """48 blocks declaring a 1024-token window, as a real Gemma header reports."""
    return ModelShape(
        architecture=architecture,
        block_count=48,
        head_count_kv=8,
        key_length=128,
        value_length=128,
        context_length=131072,
        n_vocab=262144,
        sliding_window=1024,
    )


def test_a_known_pattern_prices_only_the_global_layers_at_full_width() -> None:
    """Gemma 3 is 5 local to 1 global, so 8 of 48 layers hold the whole window.

    Worked by hand: per layer per token is 8 heads * 256 = 2048 elements at
    2 bytes = 4096 bytes. Eight global layers * 16384 cells = 512 MiB. Forty
    local layers * 1536 cells = 240 MiB. Total 752 MiB, against 3072 MiB if
    every layer were priced at full width.

    1536 rather than the window's own 1024: `llama_kv_cache_iswa` sizes a
    sliding layer as `pad256(n_swa + n_ubatch)`, because the batch being
    processed sits in the cache beside the window it attends to. Pricing the
    window alone under-states this model by 80 MiB, and under-stating is the
    direction that ships a confident badge about a model that spills.
    """
    cost = kv_cache_bytes(gemma_like("gemma3"), 16384, KvPrecision.F16)

    assert cost == 752 * MIB


def test_an_unknown_architecture_declining_to_guess_rounds_up() -> None:
    """A window with no known pattern is priced as though every layer were global.

    Over-estimating costs a pessimistic badge on one screen. Under-estimating
    ships a confident badge about a model that spills, which is the failure this
    whole phase exists to delete.
    """
    cost = kv_cache_bytes(gemma_like("something-nobody-has-seen"), 16384, KvPrecision.F16)

    assert cost == 3072 * MIB


def test_a_pattern_stated_in_the_header_beats_the_table() -> None:
    """llama.cpp reads this key before its own defaults, so a file that states
    its pattern is the authority on that model, whatever we happen to know."""
    stated = ModelShape(
        architecture="something-nobody-has-seen",
        block_count=48,
        head_count_kv=8,
        key_length=128,
        value_length=128,
        context_length=131072,
        n_vocab=262144,
        sliding_window=1024,
        sliding_window_pattern=6,
    )

    assert kv_cache_bytes(stated, 16384, KvPrecision.F16) == 752 * MIB


def test_a_pattern_stated_per_layer_is_counted_exactly() -> None:
    """The other form the same key takes. No period arithmetic at all: the file
    says which layers slide, and a model with an irregular pattern is priced
    correctly rather than rounded up to the nearest cycle."""
    shape = ModelShape(
        architecture="something-nobody-has-seen",
        block_count=4,
        head_count_kv=8,
        key_length=128,
        value_length=128,
        context_length=131072,
        n_vocab=262144,
        sliding_window=1024,
        sliding_window_layers=(True, True, True, False),
    )

    per_layer_token = 8 * 256 * 2
    expected = per_layer_token * (1 * 16384 + 3 * 1536)

    assert kv_cache_bytes(shape, 16384, KvPrecision.F16) == expected


def test_gemma_3n_is_priced_at_the_period_llama_cpp_uses() -> None:
    """Our table said 6 and llama.cpp passes 5, so every gemma3n row was priced
    with one global layer too few and read cheaper than it is."""
    at_five = kv_cache_bytes(gemma_like("gemma3n"), 16384, KvPrecision.F16)
    at_six = kv_cache_bytes(gemma_like("gemma3"), 16384, KvPrecision.F16)

    assert at_five > at_six


def test_layers_that_share_a_cache_allocate_none_of_their_own() -> None:
    """Gemma 3n reuses an earlier layer's cache on its last blocks. Charging
    those layers a cache each over-states exactly the models chosen to be cheap
    on a small machine."""
    shared = ModelShape(
        architecture="qwen3",
        block_count=48,
        head_count_kv=8,
        key_length=128,
        value_length=128,
        context_length=131072,
        n_vocab=262144,
        shared_kv_layers=16,
    )
    alone = ModelShape(
        architecture="qwen3",
        block_count=32,
        head_count_kv=8,
        key_length=128,
        value_length=128,
        context_length=131072,
        n_vocab=262144,
    )

    assert kv_cache_bytes(shared, 16384, KvPrecision.F16) == kv_cache_bytes(
        alone, 16384, KvPrecision.F16
    )
