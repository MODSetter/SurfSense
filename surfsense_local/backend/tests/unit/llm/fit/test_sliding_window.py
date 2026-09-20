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
    2 bytes = 4096 bytes. Eight global layers * 16384 tokens = 512 MiB. Forty
    local layers * 1024 tokens = 160 MiB. Total 672 MiB, against 3072 MiB if
    every layer were priced at full width. That ratio is 4.57x, which is the
    Gemma over-estimate the spec quotes at 4.6x from a separate measurement.
    """
    cost = kv_cache_bytes(gemma_like("gemma3"), 16384, KvPrecision.F16)

    assert cost == 672 * MIB


def test_an_unknown_architecture_declining_to_guess_rounds_up() -> None:
    """A window with no known pattern is priced as though every layer were global.

    Over-estimating costs a pessimistic badge on one screen. Under-estimating
    ships a confident badge about a model that spills, which is the failure this
    whole phase exists to delete.
    """
    cost = kv_cache_bytes(gemma_like("something-nobody-has-seen"), 16384, KvPrecision.F16)

    assert cost == 3072 * MIB
