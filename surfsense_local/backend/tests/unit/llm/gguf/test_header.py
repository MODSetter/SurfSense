"""Reading a model's architecture out of its GGUF header."""

import pytest

from modules.llm.gguf import TruncatedHeaderError, read_header
from tests.unit.llm.gguf.build import BOOL, FLOAT32, STRING, UINT32, array, gguf, kv

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


def test_per_layer_kv_heads_are_also_kept_layer_by_layer() -> None:
    """The widest answers "how wide can one layer be"; the cache asks what each
    layer costs and sums them, so the list has to survive the read."""
    entries = [e for e in qwen3_entries() if b"head_count_kv" not in e]
    entries.append(array("qwen3.attention.head_count_kv", UINT32, [2, 8, 8, 2]))

    assert read_header(gguf(entries)).head_count_kv_layers == (2, 8, 8, 2)


def test_a_scalar_head_count_leaves_the_per_layer_list_empty() -> None:
    """Nothing varies, so there is nothing to carry: the empty list is what
    tells the estimator to use the single number."""
    assert read_header(gguf(qwen3_entries())).head_count_kv_layers == ()


def test_a_narrower_sliding_entry_is_read_where_the_model_states_one() -> None:
    """A model may cache its window at a different width from the whole
    context, and llama.cpp charges each layer at its own."""
    entries = [
        *qwen3_entries(),
        kv("qwen3.attention.key_length_swa", UINT32, 256),
        kv("qwen3.attention.value_length_swa", UINT32, 256),
    ]
    shape = read_header(gguf(entries))

    assert shape.key_length_swa == 256
    assert shape.value_length_swa == 256


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


def test_the_widths_a_compute_buffer_is_sized_from_are_read() -> None:
    """Graph scratch scales with the widest thing a layer computes. Without
    these the estimate is one constant for every model, which under-states a
    large one by enough to flip a badge on a tight card."""
    entries = [
        *qwen3_entries(),
        kv("qwen3.embedding_length", UINT32, 2048),
        kv("qwen3.feed_forward_length", UINT32, 6144),
    ]
    shape = read_header(gguf(entries))

    assert shape.embedding_length == 2048
    assert shape.feed_forward_length == 6144


def test_a_window_pattern_stated_as_a_period_is_read() -> None:
    """llama.cpp reads this key before falling back to its own table, so a file
    that states its pattern is the authority on that model."""
    entries = [
        *qwen3_entries(),
        kv("qwen3.attention.sliding_window", UINT32, 1024),
        kv("qwen3.attention.sliding_window_pattern", UINT32, 6),
    ]
    shape = read_header(gguf(entries))

    assert shape.sliding_window_pattern == 6
    assert shape.sliding_window_layers == ()


def test_a_window_pattern_stated_per_layer_is_read_as_flags() -> None:
    """The same key carries either form. An array is the exact answer and needs
    no period arithmetic at all."""
    entries = [
        *qwen3_entries(),
        kv("qwen3.attention.sliding_window", UINT32, 1024),
        array("qwen3.attention.sliding_window_pattern", BOOL, [True, True, False]),
    ]
    shape = read_header(gguf(entries))

    assert shape.sliding_window_layers == (True, True, False)
    assert shape.sliding_window_pattern == 0


def test_layers_that_share_a_cache_are_counted() -> None:
    """Gemma 3n reuses an earlier layer's cache on its last blocks, so charging
    those layers a cache of their own over-states the window's cost."""
    entries = [*qwen3_entries(), kv("qwen3.attention.shared_kv_layers", UINT32, 10)]

    assert read_header(gguf(entries)).shared_kv_layers == 10


def test_a_latent_attention_model_reports_its_compressed_widths() -> None:
    """DeepSeek-class models cache one compressed entry per token per layer, not
    a key and a value per head. Priced by the usual formula they read far too
    large."""
    entries = [
        *qwen3_entries(),
        kv("qwen3.attention.kv_lora_rank", UINT32, 512),
        kv("qwen3.attention.key_length_mla", UINT32, 64),
    ]
    shape = read_header(gguf(entries))

    assert shape.kv_lora_rank == 512
    assert shape.key_length_mla == 64


def test_an_older_header_without_the_new_fields_still_reads() -> None:
    """Every field added for a sharper estimate is optional, and its absence
    prices the conservative way rather than zero."""
    shape = read_header(gguf(qwen3_entries()))

    assert shape.embedding_length == 0
    assert shape.feed_forward_length == 0
    assert shape.kv_lora_rank == 0
    assert shape.block_count == 28


def test_unknown_value_types_do_not_stop_the_parse() -> None:
    """Uploaders put arbitrary keys in headers, and one we cannot read is not a
    reason to refuse a model we can otherwise price."""
    entries = [*qwen3_entries(), kv("some.vendor.metric", FLOAT32, 0.5)]

    assert read_header(gguf(entries)).block_count == 28
