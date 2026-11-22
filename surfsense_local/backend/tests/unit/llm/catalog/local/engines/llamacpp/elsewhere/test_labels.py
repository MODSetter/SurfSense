"""What a found file is called on the screen, read from its own header.

Another app's file names are its own business: Ollama's are content hashes and
Jan names every model `model.gguf`. The header names the model, counts its
parameters in its tensor table and states its quantization, so those are read;
the file name is consulted only for the quantizer's label, which no header holds.
"""

from pathlib import Path

import pytest

from modules.llm.catalog.local.engines.llamacpp.elsewhere.labels import label_of
from modules.llm.gguf import read_header_prefix
from tests.unit.llm.catalog.local.engines.llamacpp.elsewhere.files import (
    Q4_K_M,
    chat_model_bytes,
)

pytestmark = pytest.mark.unit

BLOB = Path("/home/ana/.ollama/models/blobs/sha256-" + "ab" * 32)


def _header(**fields):
    return read_header_prefix(chat_model_bytes(**fields))


def test_a_model_is_named_by_its_header() -> None:
    """`general.name` names the model and `general.architecture` its kind."""
    label = label_of(_header(name="Qwen3 8B"), Path("/m/Qwen3-8B-Q4_K_M.gguf"))

    assert label.name == "Qwen3 8B"
    assert label.architecture == "qwen3"


def test_an_ollama_model_is_named_by_the_tag_its_user_pulled() -> None:
    """The tag a person pulled wins over the header's own name."""
    label = label_of(_header(name="Qwen3 8B"), BLOB, name="qwen3:8b")

    assert label.name == "qwen3:8b"


def test_a_model_whose_header_names_nothing_is_named_by_its_file() -> None:
    """With no name in the header, the file's own name is the label."""
    label = label_of(_header(name=None), Path("/m/my-finetune-Q5_K_M.gguf"))

    assert label.name == "my-finetune-Q5_K_M"


def test_a_file_called_model_is_named_by_its_folder() -> None:
    """Jan keeps each model as `<model id>/model.gguf`."""
    path = Path("/jan/data/llamacpp/models/Jan-v3.5-4B-Q4_K_XL/model.gguf")

    assert label_of(_header(name=None), path).name == "Jan-v3.5-4B-Q4_K_XL"


def test_parameters_are_counted_from_the_tensor_table() -> None:
    """Parameters are the product of each tensor's dimensions, summed."""
    header = _header(
        tensors=[
            ("token_embd.weight", [4096, 151936]),
            ("blk.0.attn_q.weight", [4096, 4096]),
        ]
    )

    label = label_of(header, Path("/m/a.gguf"))

    assert label.parameters == 4096 * 151936 + 4096 * 4096


def test_the_quantizers_label_comes_from_the_file_name() -> None:
    """`UD-Q4_K_XL` is Unsloth's name; the header calls the same file Q4_K_M."""
    label = label_of(_header(file_type=Q4_K_M), Path("/m/Qwen3-8B-UD-Q4_K_XL.gguf"))

    assert label.quantization == "UD-Q4_K_XL"


def test_a_file_named_by_its_hash_takes_its_quantization_from_the_header() -> None:
    """An Ollama blob's quantization is `general.file_type`, since its name is a hash."""
    assert label_of(_header(file_type=Q4_K_M), BLOB).quantization == "Q4_K_M"


def test_a_folder_named_after_its_build_names_the_quantization() -> None:
    """Jan's folder carries the build's label when its file is just `model.gguf`."""
    path = Path("/jan/data/llamacpp/models/Jan-v3.5-4B-Q4_K_XL/model.gguf")

    assert label_of(_header(file_type=Q4_K_M), path).quantization == "Q4_K_XL"


def test_a_file_that_states_no_quantization_says_so() -> None:
    """No label in the name or the header is `unknown`, never a guess."""
    assert label_of(_header(file_type=None), BLOB).quantization == "unknown"


def test_the_context_is_the_window_the_model_was_trained_for() -> None:
    """The context is `<architecture>.context_length`, as the header states it."""
    assert label_of(_header(context=262144), BLOB).context == 262144
