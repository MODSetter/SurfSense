"""What a found file is called on the screen, and what its header says about it.

A model is called what a person would recognise: an Ollama tag, else the file's
own name less its build, as LM Studio and Hugging Face show it. Ollama's names
are hashes and Jan names every model `model.gguf`, so those fall back to the
header's `general.name`, then the folder. Parameters, quantization and window
come from the header.
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


def test_a_file_another_app_named_is_called_by_that_name_less_its_build() -> None:
    """The name a person sees in LM Studio, without the build it also shows."""
    label = label_of(_header(name="Qwen3 8B"), Path("/m/Qwen3-8B-Q4_K_M.gguf"))

    assert label.name == "Qwen3-8B"
    assert label.architecture == "qwen3"


@pytest.mark.parametrize(
    ("file", "name"),
    [
        ("Qwen3.5-4B-UD-Q4_K_XL.gguf", "Qwen3.5-4B"),
        ("SmolLM2-135M-Instruct-Q4_0.gguf", "SmolLM2-135M-Instruct"),
        ("llama3.1-heretic.Q2_K.gguf", "llama3.1-heretic"),
        ("big-Q4_K_M-00001-of-00003.gguf", "big"),
        ("my-finetune.gguf", "my-finetune"),
    ],
)
def test_the_build_and_the_split_come_off_a_file_name(file: str, name: str) -> None:
    """Measured: one SmolLM2 Instruct header names itself after a training run."""
    header = _header(name="Smollm2 135M 8k Lc100K Mix1 Ep2")

    assert label_of(header, Path("/m") / file).name == name


def test_a_file_named_by_its_hash_is_named_by_its_header() -> None:
    """An Ollama blob picked by hand has no tag and a hash for a name."""
    assert label_of(_header(name="Qwen3 8B"), BLOB).name == "Qwen3 8B"


def test_a_file_called_model_is_named_by_its_header() -> None:
    """Jan's file is `model.gguf`; its header names the model."""
    path = Path("/jan/data/llamacpp/models/Jan-v3.5-4B-Q4_K_XL/model.gguf")

    assert label_of(_header(name="Jan-v3.5-4B"), path).name == "Jan-v3.5-4B"


def test_an_ollama_model_is_named_by_the_tag_its_user_pulled() -> None:
    """The tag a person pulled wins over the header's own name."""
    label = label_of(_header(name="Qwen3 8B"), BLOB, name="qwen3:8b")

    assert label.name == "qwen3:8b"


def test_a_file_called_model_whose_header_names_nothing_is_named_by_its_folder() -> (
    None
):
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
