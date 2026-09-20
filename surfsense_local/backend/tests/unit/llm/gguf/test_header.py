"""Reading a model's architecture out of its GGUF header."""

import pytest

from modules.llm.gguf import TruncatedHeaderError, read_header
from tests.unit.llm.gguf.build import FLOAT32, STRING, UINT32, array, gguf, kv

pytestmark = pytest.mark.unit


def qwen3_entries() -> list[bytes]:
    """The fields a fit estimate needs, named as Qwen3 headers name them."""
    return [
        kv("general.architecture", STRING, "qwen3"),
        kv("qwen3.block_count", UINT32, 28),
        kv("qwen3.attention.head_count_kv", UINT32, 8),
        kv("qwen3.attention.key_length", UINT32, 128),
        kv("qwen3.attention.value_length", UINT32, 128),
        kv("qwen3.context_length", UINT32, 40960),
        array("tokenizer.ggml.tokens", STRING, ["a", "b", "c"]),
    ]


def test_a_header_yields_the_shape_a_fit_estimate_needs() -> None:
    """Everything `need` is computed from, and nothing else."""
    shape = read_header(gguf(qwen3_entries()))

    assert shape.architecture == "qwen3"
    assert shape.block_count == 28
    assert shape.head_count_kv == 8
    assert shape.context_length == 40960
    assert shape.n_vocab == 3


def test_a_model_without_a_sliding_window_reports_none() -> None:
    """Zero means full attention on every layer, which is the common case."""
    assert read_header(gguf(qwen3_entries())).sliding_window == 0


def test_per_layer_kv_heads_are_read_as_the_widest_layer() -> None:
    """`head_count_kv` is scalar or array. An array means per-layer heads, and
    collapsing it to its first element under-prices a hybrid model's cache."""
    entries = [e for e in qwen3_entries() if b"head_count_kv" not in e]
    entries.append(array("qwen3.attention.head_count_kv", UINT32, [2, 8, 8, 2]))

    assert read_header(gguf(entries)).head_count_kv == 8


def test_a_truncated_header_says_so_rather_than_guessing() -> None:
    """The caller retries with a wider range; a partial parse would ship a
    confident number derived from half a file."""
    whole = gguf(qwen3_entries())

    with pytest.raises(TruncatedHeaderError):
        read_header(whole[: len(whole) // 2])


def test_something_that_is_not_a_gguf_is_rejected() -> None:
    """A wrong file is a rejection, unlike a short one, which is a wider read."""
    with pytest.raises(ValueError):
        read_header(b"not a gguf file at all")


def test_a_mixture_of_experts_reports_its_expert_counts() -> None:
    """Without these an MoE entry's speed prediction is wrong by roughly 10x."""
    entries = [
        *qwen3_entries(),
        kv("qwen3.expert_count", UINT32, 128),
        kv("qwen3.expert_used_count", UINT32, 8),
    ]
    shape = read_header(gguf(entries))

    assert shape.expert_count == 128


def test_unknown_value_types_do_not_stop_the_parse() -> None:
    """Uploaders put arbitrary keys in headers, and one we cannot read is not a
    reason to refuse a model we can otherwise price."""
    entries = [*qwen3_entries(), kv("some.vendor.metric", FLOAT32, 0.5)]

    assert read_header(gguf(entries)).block_count == 28
