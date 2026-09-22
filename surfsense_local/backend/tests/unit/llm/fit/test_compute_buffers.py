"""Graph scratch: the third term, and the one that was a constant.

The measured points are what llama.cpp reported as its compute buffer at
b11050. A constant line passing through the smallest of them under-states a 4B
by roughly 70 MiB, which is more than the margin that decided a 12 GB card's
top row.
"""

import pytest

from modules.llm.fit import ModelShape, compute_buffer_bytes

pytestmark = pytest.mark.unit

MIB = 1024**2


def qwen3(blocks: int, embedding: int, feed_forward: int) -> ModelShape:
    """A dense Qwen3, whose widths are what the scratch term is sized from."""
    return ModelShape(
        architecture="qwen3",
        block_count=blocks,
        head_count_kv=8,
        key_length=128,
        value_length=128,
        context_length=40960,
        n_vocab=151936,
        embedding_length=embedding,
        feed_forward_length=feed_forward,
    )


QWEN3_1_7B = qwen3(28, 2048, 6144)
QWEN3_4B = qwen3(36, 2560, 9728)


def test_a_wider_model_needs_more_scratch_at_the_same_window() -> None:
    """The whole point. A constant charged these two the same and was wrong
    about at least one of them."""
    narrow = compute_buffer_bytes(QWEN3_1_7B, 16384)
    wide = compute_buffer_bytes(QWEN3_4B, 16384)

    assert wide > narrow


@pytest.mark.parametrize(
    ("shape", "n_ctx", "measured_mib"),
    [
        (QWEN3_1_7B, 16384, 102.24),  # Metal, b11050
        (QWEN3_1_7B, 40960, 222.24),  # Metal, same run
        (QWEN3_4B, 16384, 169.63),  # Vulkan: 143.62 device plus 26.01 host
    ],
)
def test_no_measured_point_is_under_predicted(shape, n_ctx, measured_mib) -> None:
    """The rule the whole estimator runs on, pinned to every point we have.

    Over-stating costs a pessimistic badge, which a user can install through.
    Under-stating ships a confident badge about a model that spills, so this
    asserts a floor rather than a match. The safety factor is fitted to keep
    every one of these on the safe side.
    """
    assert compute_buffer_bytes(shape, n_ctx) >= measured_mib * MIB


def test_scratch_is_never_priced_at_zero_when_the_widths_are_missing() -> None:
    """A searched header can omit them. Zero would be the one answer that is
    certainly wrong, so the old constant line is the floor in that case."""
    unknown = ModelShape(
        architecture="something-nobody-has-seen",
        block_count=28,
        head_count_kv=8,
        key_length=128,
        value_length=128,
        context_length=40960,
        n_vocab=151936,
    )

    assert compute_buffer_bytes(unknown, 16384) > 0


def test_scratch_grows_with_the_window() -> None:
    """Part of it is the attention mask, which is context shaped."""
    at_floor = compute_buffer_bytes(QWEN3_4B, 16384)
    at_full = compute_buffer_bytes(QWEN3_4B, 40960)

    assert at_full > at_floor


def test_a_mixture_of_experts_is_sized_by_what_one_token_activates() -> None:
    """A router reads a few experts per token, and the graph holds those. Priced
    by the dense width alone, a model built to be cheap reads cheaper still."""
    dense = qwen3(48, 2048, 6144)
    moe = ModelShape(
        architecture="qwen3moe",
        block_count=48,
        head_count_kv=8,
        key_length=128,
        value_length=128,
        context_length=40960,
        n_vocab=151936,
        embedding_length=2048,
        feed_forward_length=6144,
        expert_count=128,
        expert_used_count=8,
        expert_feed_forward_length=768,
    )

    assert compute_buffer_bytes(moe, 16384) > compute_buffer_bytes(dense, 16384)
