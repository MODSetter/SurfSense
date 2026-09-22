"""What a GGUF says it is, read from the file rather than guessed from its name.

Three different things used to answer this question, all by guessing:
`list_builds` matched `"mmproj"` in the path, `projector.py` matched the same
string again, and the gate asked Hugging Face, which parses one file per repo
and serves that as the repo's answer.

The last one is how 17 of the 1000 most downloaded repos come to be refused
today. `Jackrong/Qwen3.8-27B-MTP-GGUF` ships twelve builds of a Qwen 3.5 chat
model beside one vision sidecar. Hugging Face read the sidecar, reported the
repo as `clip`, and the whole thing is turned away with "This is the vision half
of another model", advice that cannot be followed because the model it belongs
to is that repo.

GGUF answers this itself. `general.type` is an official key with an official
enum in `gguf.constants.GGUFType`, and real files populate it: both projectors
measured on the hub carry `general.type='mmproj'`.

The truncation rule is the other half. A projector has no tokenizer, so its
header fits in a small prefix and parses. A chat model's `tokenizer.ggml.tokens`
runs to megabytes, so the same prefix cuts mid metadata. Measured: Qwen3 0.6B
5.93 MB, Llama 3.2 1B 7.82 MB. A header that does not fit is therefore a real
model, which makes the cheap read and the safe answer the same read.
"""

import pytest

from modules.llm.gguf.file_kind import PROBE_BYTES, FileKind, file_kind
from tests.unit.llm.gguf.build import STRING, UINT32, gguf, kv

pytestmark = pytest.mark.unit


def test_a_projector_says_so_whatever_it_is_called() -> None:
    """The bug this replaces, stated as a contract: the name is not consulted."""
    raw = gguf([kv("general.type", STRING, "mmproj"),
                kv("general.architecture", STRING, "clip")])

    assert file_kind(raw).kind is FileKind.PROJECTOR


def test_a_model_says_so() -> None:
    """The ordinary case for a small model whose header does fit."""
    raw = gguf([kv("general.type", STRING, "model"),
                kv("general.architecture", STRING, "qwen3")])

    kind = file_kind(raw)

    assert kind.kind is FileKind.MODEL
    assert kind.architecture == "qwen3"


def test_a_header_too_big_for_the_prefix_is_a_model() -> None:
    """The measured rule, and the reason the refusal path is the cheap one.

    A chat model's vocabulary pushes its metadata past any prefix worth
    fetching. Nothing else in a repo does that, so a truncated read is not a
    failure to answer, it is the answer.
    """
    raw = gguf([kv("general.type", STRING, "model"),
                kv("general.architecture", STRING, "qwen3")])

    assert file_kind(raw[:20]).kind is FileKind.MODEL


def test_a_file_that_is_not_a_gguf_at_all_is_a_model() -> None:
    """Fails open, like every other step. A refusal is never made from a
    failure to read, because the runtime is the authority and it will refuse
    with the same sentence if this is wrong."""
    assert file_kind(b"this is not a gguf").kind is FileKind.MODEL


def test_an_older_file_with_no_type_key_falls_back_to_the_architecture() -> None:
    """`general.type` postdates GGUF v1. A file without it is judged the way
    everything was judged before, by what it declares itself to be."""
    raw = gguf([kv("general.architecture", STRING, "clip")])

    kind = file_kind(raw)

    assert kind.kind is FileKind.PROJECTOR
    assert kind.architecture == "clip"


def test_an_imatrix_and_an_adapter_are_named_too() -> None:
    """Both are valid GGUF containers holding something that is not a model, so
    only the header separates them. `list_builds` matches neither by name."""
    assert file_kind(gguf([kv("general.type", STRING, "imatrix")])).kind is FileKind.IMATRIX
    assert file_kind(gguf([kv("general.type", STRING, "adapter")])).kind is FileKind.ADAPTER


def test_a_shard_is_recognised_from_its_split_keys() -> None:
    """`-of-` in a filename is the guess this replaces. `split.count` is the
    file saying it."""
    raw = gguf([kv("general.type", STRING, "model"),
                kv("general.architecture", STRING, "qwen3"),
                kv("split.count", UINT32, 4)])

    assert file_kind(raw).kind is FileKind.SHARD


def test_the_probe_is_small_enough_that_a_refusal_is_cheaper_than_a_pricing_read() -> None:
    """The economics that make this worth doing at all. Today a refusal costs
    nothing and is wrong 1.7% of the time; this makes it cost a quarter of a
    megabyte and be right."""
    assert PROBE_BYTES <= 512 * 1024


def test_a_header_that_parsed_and_named_no_architecture_cannot_be_loaded() -> None:
    """The one case where silence is an answer rather than a missing answer.

    `general.architecture` is mandatory for anything llama.cpp can load: it is
    what the loader dispatches on. A file that declares none will fail every
    time. Measured on the hub: MiniMax-H3's video GGUFs carry a bare tensor
    header with zero metadata, and they are among the repos that install and
    then fail today.

    Safe only because the parse succeeded. A short read raises before reaching
    this, which is what separates "I read it and there was nothing" from "I
    could not finish reading", and the second must always admit.
    """
    raw = gguf([kv("general.type", STRING, "model")])

    assert file_kind(raw).kind is FileKind.NOT_LOADABLE


def test_a_bare_tensor_header_with_no_metadata_cannot_be_loaded() -> None:
    """The measured shape: a valid GGUF container holding nothing that says
    what it is."""
    assert file_kind(gguf([])).kind is FileKind.NOT_LOADABLE


def test_a_truncated_read_still_admits() -> None:
    """The line this must never cross. A chat model's word list pushes its
    header past any prefix worth fetching, so truncation is the common case and
    refusing on it would refuse almost everything."""
    raw = gguf([kv("general.type", STRING, "model"),
                kv("general.architecture", STRING, "qwen3")])

    assert file_kind(raw[:20]).kind is FileKind.MODEL
