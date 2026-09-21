"""How much of a build a router reads per decoded token.

Authoring time code, but the number it writes goes into the shipped manifest and
feeds a speed estimate, so an expert tensor it fails to recognise reports a
mixture of experts as dense and over-states what the model costs to run.
"""

import pytest
from curated.tensor_bytes import decode_fraction, is_expert, tensor_bytes
from gguf.constants import MODEL_TENSOR, TENSOR_NAMES

from modules.llm.gguf import GgufHeader, HeaderTensor

pytestmark = pytest.mark.unit

F32, Q4_K = 0, 12


def header(*tensors: HeaderTensor) -> GgufHeader:
    """A header carrying nothing but a tensor table, which is all this reads."""
    return GgufHeader(metadata={}, tensors=tensors)


def test_the_expert_names_come_from_llama_cpps_own_table() -> None:
    """Not restated here. A rename upstream has to break the import rather than
    quietly stop matching, because a miss reads as a dense model."""
    assert is_expert(TENSOR_NAMES[MODEL_TENSOR.FFN_UP_EXP].format(bid=0))
    assert is_expert(TENSOR_NAMES[MODEL_TENSOR.FFN_DOWN_CHEXP].format(bid=7))


def test_a_stored_tensor_carries_a_suffix_the_table_does_not() -> None:
    """The table names `blk.{bid}.ffn_up_exps`; a file stores
    `blk.0.ffn_up_exps.weight`. Comparing whole names would match neither."""
    assert is_expert("blk.0.ffn_up_exps.weight")


def test_the_per_expert_norm_is_not_counted_as_an_expert_weight() -> None:
    """llama.cpp's own MoE pattern covers the seven matrices and not this, and
    the set that decides what it moves to the host is the set that decides what
    it reads back from the host."""
    assert not is_expert("blk.0.ffn_norm_exps.weight")


def test_an_ordinary_dense_tensor_is_not_mistaken_for_one() -> None:
    """`ffn_up` is not `ffn_up_exps`, and a substring test would say it is."""
    assert not is_expert("blk.0.ffn_up.weight")
    assert not is_expert("blk.0.attn_q.weight")
    assert not is_expert("token_embd.weight")


def test_a_dense_model_reads_every_byte_it_holds() -> None:
    """Exactly 1.0, so the field is safe to write for every entry."""
    dense = header(
        HeaderTensor("blk.0.attn_q.weight", (4096, 4096), F32),
        HeaderTensor("blk.0.ffn_up.weight", (4096, 11008), F32),
    )

    assert decode_fraction(dense, expert_used_count=0, expert_count=0) == 1.0


def test_only_the_experts_a_router_picks_are_counted() -> None:
    """Eight experts, two read. The shared weights are read whole, so the answer
    is between the activated share and one rather than either of them."""
    shared = HeaderTensor("blk.0.attn_q.weight", (64, 64), F32)
    experts = HeaderTensor("blk.0.ffn_up_exps.weight", (64, 64, 8), F32)
    both = header(shared, experts)

    shared_bytes = tensor_bytes(shared)
    expert_bytes = tensor_bytes(experts)
    expected = (shared_bytes + expert_bytes * 0.25) / (shared_bytes + expert_bytes)

    assert decode_fraction(both, 2, 8) == round(expected, 4)


def test_a_model_that_routes_to_every_expert_reads_everything() -> None:
    """Used equals total is dense in all but name, and dividing by it would
    report a saving that is not there."""
    moe = header(HeaderTensor("blk.0.ffn_up_exps.weight", (64, 64, 8), F32))

    assert decode_fraction(moe, 8, 8) == 1.0


def test_a_quantized_expert_is_sized_by_its_own_block_layout() -> None:
    """The ratio is over bytes, and experts are not always quantized like the
    rest of the file, so a parameter count would answer a different question."""
    quantized = HeaderTensor("blk.0.ffn_up_exps.weight", (256, 256, 8), Q4_K)
    full = HeaderTensor("blk.0.ffn_up_exps.weight", (256, 256, 8), F32)

    assert tensor_bytes(quantized) < tensor_bytes(full)


def test_a_tensor_type_this_build_cannot_size_is_skipped_not_fatal() -> None:
    """ggml adds types, and one we cannot price is one tensor missing from a
    ratio rather than a header to refuse."""
    assert tensor_bytes(HeaderTensor("blk.0.ffn_up_exps.weight", (64, 64), 9999)) == 0
