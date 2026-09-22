"""The adapter that lets llama.cpp's own parser read a header with no weights.

Two private methods of `GGUFReader` are overridden, so this file is the contract
that says what those overrides must do. It also pins the package version: the
methods are private upstream and a bump is only safe once these still pass.
"""

from importlib.metadata import version

import pytest

from modules.llm.gguf import HeaderTensor, TruncatedHeaderError, read_header_prefix
from tests.unit.llm.gguf.build import STRING, UINT32, array, gguf, kv, tensor

pytestmark = pytest.mark.unit

# F32 and Q4_K as ggml numbers them, so the table can be checked without the enum.
F32, Q4_K = 0, 12


def entries() -> list[bytes]:
    """The smallest header that is still a valid one."""
    return [
        kv("general.architecture", STRING, "qwen3"),
        kv("qwen3.block_count", UINT32, 28),
        array("tokenizer.ggml.tokens", STRING, ["a", "b", "c"]),
    ]


def test_the_pinned_version_is_the_one_these_overrides_were_written_against() -> None:
    """`_get` and `_build_tensors` are private upstream.

    Failing here is the signal to re-read them before taking the new version,
    not a reason to widen the pin.
    """
    assert version("gguf") == "0.19.0"


def test_a_header_without_its_weights_parses() -> None:
    """The whole point: a prefix stops where the tensor data would start, and
    the base class would slice into bytes that were never downloaded."""
    header = read_header_prefix(gguf(entries(), [tensor("blk.0.attn_q.weight", [64, 64])]))

    assert header.metadata["general.architecture"] == "qwen3"
    assert header.metadata["qwen3.block_count"] == 28


def test_the_tensor_table_keeps_names_dimensions_and_types() -> None:
    """Sizing an expert or finding a projector reads the table, never the data."""
    tensors = [
        tensor("blk.0.attn_q.weight", [64, 128], dtype=F32),
        tensor("blk.0.ffn_up_exps.weight", [128, 256, 8], dtype=Q4_K),
    ]

    header = read_header_prefix(gguf(entries(), tensors))

    assert header.tensors == (
        HeaderTensor("blk.0.attn_q.weight", (64, 128), F32),
        HeaderTensor("blk.0.ffn_up_exps.weight", (128, 256, 8), Q4_K),
    )


def test_a_prefix_that_stops_inside_the_header_says_so() -> None:
    """numpy shortens a slice past the end instead of raising, so without the
    bounds check this would parse into a confident wrong shape."""
    whole = gguf(entries())

    with pytest.raises(TruncatedHeaderError):
        read_header_prefix(whole[: len(whole) // 2])


def test_a_prefix_that_stops_inside_the_tensor_table_says_so() -> None:
    """The table sits after the metadata, so a read can be long enough for one
    and short for the other. Both are a wider read, not a rejection."""
    whole = gguf(entries(), [tensor("blk.0.attn_q.weight", [64, 64])])

    with pytest.raises(TruncatedHeaderError):
        read_header_prefix(whole[:-8])


def test_the_reader_leaves_no_temporary_file_behind(tmp_path, monkeypatch) -> None:
    """It writes the prefix to disk to hand the parser a path, once per searched
    model, so a leak here would be one file per row the user scrolls past."""
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))

    read_header_prefix(gguf(entries()))
    with pytest.raises(TruncatedHeaderError):
        read_header_prefix(gguf(entries())[:20])

    assert list(tmp_path.iterdir()) == []
