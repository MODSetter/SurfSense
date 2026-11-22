"""Which files another app downloaded the bundled llama.cpp can chat with.

A file in SurfSense's own folder was put there for SurfSense, so the catalog
fails open on what it cannot place. A file in Ollama's or LM Studio's folder was
not, and those apps run formats llama.cpp does not: Ollama names some
architectures its own way and keeps a multimodal model's vision tower inside its
weights. So a found file is offered only on the header's own evidence.
"""

from pathlib import Path

import pytest
from gguf.constants import MODEL_ARCH, MODEL_ARCH_NAMES, MODEL_TENSORS, TENSOR_NAMES

from modules.llm.catalog.local.engines.llamacpp.elsewhere.runs_here import (
    COMPANION_TENSOR_PREFIXES,
    UnusableCode,
    unusable,
)
from modules.llm.gguf import read_header_prefix
from modules.llm.providers.llamacpp.preset import preset_can_name
from tests.unit.llm.catalog.local.engines.llamacpp.elsewhere.files import (
    chat_model_bytes,
)
from tests.unit.llm.gguf.build import BOOL, STRING, UINT32, gguf, kv

pytestmark = pytest.mark.unit


def test_a_chat_model_llamacpp_builds_is_usable() -> None:
    """A chat architecture llama.cpp names, with no companion tensors, is offered."""
    assert unusable(read_header_prefix(chat_model_bytes())) is None


def test_a_projector_is_never_offered_as_a_model() -> None:
    """A projector is half of another model, not one to chat with."""
    projector = gguf(
        [
            kv("general.type", STRING, "mmproj"),
            kv("general.architecture", STRING, "clip"),
            kv("clip.has_vision_encoder", BOOL, True),
        ]
    )

    found = unusable(read_header_prefix(projector))

    assert found is not None
    assert found.code is UnusableCode.NOT_A_MODEL


def test_an_embedder_is_not_offered_and_keeps_the_classifiers_reason() -> None:
    """Jan keeps an embedder beside its chat models; it cannot answer."""
    embedder = gguf(
        [
            kv("general.architecture", STRING, "bert"),
            kv("bert.block_count", UINT32, 6),
        ]
    )

    found = unusable(read_header_prefix(embedder))

    assert found is not None
    assert found.code == "embedder"
    assert "search" in found.reason


def test_an_architecture_llamacpp_does_not_name_is_not_offered() -> None:
    """Ollama writes gpt-oss as `gptoss`; llama.cpp's loader knows `gpt-oss`."""
    found = unusable(read_header_prefix(chat_model_bytes(architecture="gptoss")))

    assert found is not None
    assert found.code is UnusableCode.UNKNOWN_ARCHITECTURE


def test_a_model_holding_its_own_vision_tower_is_not_offered() -> None:
    """Ollama's multimodal files keep the projector's tensors in the weights,
    and llama.cpp's loader refuses a file with tensors it did not create."""
    combined = chat_model_bytes(
        architecture="gemma3",
        tensors=[
            ("token_embd.weight", [4096, 3]),
            ("v.blk.0.attn_q.weight", [1152, 1152]),
            ("mm.input_projection.weight", [1152, 4096]),
        ],
    )

    found = unusable(read_header_prefix(combined))

    assert found is not None
    assert found.code is UnusableCode.VISION_INSIDE


def test_only_the_projector_architecture_owns_the_companion_tensor_names() -> None:
    """The vision check reads tensor names, so it holds only while llama.cpp's
    own table gives these prefixes to projectors and to no chat model."""
    owners = {
        MODEL_ARCH_NAMES[arch]
        for arch, tensors in MODEL_TENSORS.items()
        for t in tensors
        if t in TENSOR_NAMES and TENSOR_NAMES[t].startswith(COMPANION_TENSOR_PREFIXES)
    }

    assert owners == {MODEL_ARCH_NAMES[MODEL_ARCH.MMPROJ]}


def test_the_first_part_of_a_split_build_is_the_model() -> None:
    """The first part of a split build is the model; a later part is not."""
    first = chat_model_bytes(split=(0, 3))
    later = chat_model_bytes(split=(1, 3))

    assert unusable(read_header_prefix(first)) is None
    later_found = unusable(read_header_prefix(later))
    assert later_found is not None
    assert later_found.code is UnusableCode.NOT_A_MODEL


def test_a_file_that_would_not_parse_is_not_offered() -> None:
    """A file another app wrote that will not parse fails closed."""
    found = unusable(None)

    assert found is not None
    assert found.code is UnusableCode.UNREADABLE


@pytest.mark.parametrize(
    "path",
    [
        r"C:\Users\Ana Lima\.ollama\models\blobs\sha256-ab12",
        "/Users/ana/.lmstudio/models/unsloth/Qwen3-8B-GGUF/Qwen3 8B [Q4].gguf",
        "/home/ana/models/x=y/model.gguf",
    ],
)
def test_the_preset_names_an_ordinary_path(path: str) -> None:
    """Spaces, brackets and `=` survive the preset's parser."""
    assert preset_can_name(Path(path))


@pytest.mark.parametrize(
    "path",
    [
        "/home/ana/models #1/model.gguf",
        r"C:\models;old\model.gguf",
        "/home/ana/a\nb/model.gguf",
    ],
)
def test_the_preset_cannot_name_a_path_its_parser_would_cut(path: str) -> None:
    """Measured at b11050: llama.cpp's preset parser ends a value at `#` or `;`,
    quoted or not, and the worker then fails to open what is left."""
    assert not preset_can_name(Path(path))
