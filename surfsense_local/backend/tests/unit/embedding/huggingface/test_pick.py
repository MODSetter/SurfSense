"""Which files of a Hugging Face repo an embedder is downloaded as, and whether
the repo may be downloaded at all."""

import pytest

from modules.embedding.huggingface.pick import (
    NotAnEmbedderCode,
    NotRunnableError,
    pick_files,
    scan_verdict,
)
from modules.llm.catalog.local.classifier import NotRunnableCode
from modules.llm.catalog.local.install.codes import InstallCode
from modules.llm.catalog.local.listed_file import ListedFile

pytestmark = pytest.mark.unit

H = "a" * 64


def listing(*paths: str) -> list[ListedFile]:
    """Each path hashed, as Hugging Face lists LFS files."""
    return [ListedFile(path, 1000, H) for path in paths]


def test_a_generic_int8_build_comes_first() -> None:
    """Smaller and faster than full precision on a CPU, as measured."""
    picked = pick_files(
        listing("onnx/model.onnx", "onnx/model_int8.onnx", "tokenizer.json")
    )

    assert picked.weights.path == "onnx/model_int8.onnx"
    assert picked.tokenizer.path == "tokenizer.json"


def test_full_precision_when_no_generic_int8_exists() -> None:
    """The original export when no portable quantisation exists."""
    picked = pick_files(listing("model.onnx", "tokenizer.json"))

    assert picked.weights.path == "model.onnx"


@pytest.mark.parametrize(
    "path",
    [
        "onnx/model_qint8_avx512_vnni.onnx",
        "onnx/model_quint8_avx2.onnx",
        "onnx/model_O4.onnx",
        "onnx/model_fp16.onnx",
        "onnx/model_q4.onnx",
        "onnx/model_bnb4.onnx",
    ],
)
def test_a_build_for_one_cpu_or_other_hardware_is_never_taken(path: str) -> None:
    """Tuned for one CPU, made for a GPU, or fp16, which is slow on a CPU."""
    with pytest.raises(NotRunnableError):
        pick_files(listing(path, "tokenizer.json"))


def test_external_data_downloads_with_its_model() -> None:
    """A large export keeps its weights beside the graph, under its name."""
    picked = pick_files(
        listing(
            "onnx/model_quantized.onnx",
            "onnx/model_quantized.onnx_data",
            "onnx/model.onnx",
            "onnx/model.onnx_data",
            "tokenizer.json",
        )
    )

    assert [f.path for f in picked.data] == ["onnx/model_quantized.onnx_data"]


def test_a_repo_without_onnx_or_a_tokenizer_cannot_run() -> None:
    """Either missing, the encoder cannot read a passage."""
    with pytest.raises(NotRunnableError, match="ONNX"):
        pick_files(listing("model.safetensors", "tokenizer.json"))
    with pytest.raises(NotRunnableError, match="tokenizer"):
        pick_files(listing("onnx/model.onnx"))


def test_an_unhashed_file_cannot_be_checked_after_download() -> None:
    """A download nothing can check would be trusted blind."""
    with pytest.raises(NotRunnableError):
        pick_files(
            [ListedFile("onnx/model.onnx", 1000, None), *listing("tokenizer.json")]
        )


def test_a_refusal_the_interface_can_word_names_its_code() -> None:
    """The interface words these two in the reader's language, by the code."""
    with pytest.raises(NotRunnableError) as no_onnx:
        pick_files(listing("model.safetensors", "tokenizer.json"))
    with pytest.raises(NotRunnableError) as no_tokenizer:
        pick_files(listing("onnx/model.onnx"))

    assert no_onnx.value.code is NotAnEmbedderCode.NO_ONNX
    assert no_tokenizer.value.code is NotAnEmbedderCode.NO_TOKENIZER


def test_the_unhashed_file_s_sentence_has_no_code() -> None:
    """It names the file, which a code alone cannot carry, so it travels as it
    is written."""
    with pytest.raises(NotRunnableError) as unhashed:
        pick_files(
            [ListedFile("onnx/model.onnx", 1000, None), *listing("tokenizer.json")]
        )

    assert unhashed.value.code is None
    assert str(unhashed.value) == "Hugging Face lists no checksum for onnx/model.onnx."


def test_a_repo_s_code_is_never_a_model_s_or_an_install_s() -> None:
    """All three travel to one interface, and a row carries either of the first
    two in one field, so no value may mean two things."""
    ours = {c.value for c in NotAnEmbedderCode}

    assert not ours & {c.value for c in NotRunnableCode}
    assert not ours & {c.value for c in InstallCode}


def test_a_repo_hugging_face_flags_is_refused() -> None:
    """Hugging Face's own scan: unsafe anywhere, or any flag on a file we take."""
    clean = {"scansDone": True, "filesWithIssues": []}
    unsafe_elsewhere = {
        "scansDone": True,
        "filesWithIssues": [{"path": "danger.pkl", "level": "unsafe"}],
    }
    caution_on_ours = {
        "scansDone": True,
        "filesWithIssues": [{"path": "onnx/model.onnx", "level": "caution"}],
    }
    caution_elsewhere = {
        "scansDone": True,
        "filesWithIssues": [{"path": "build.py", "level": "caution"}],
    }
    ours = {"onnx/model.onnx", "tokenizer.json"}

    assert scan_verdict(clean, ours) is None
    assert scan_verdict(caution_elsewhere, ours) is None
    assert scan_verdict(unsafe_elsewhere, ours)
    assert scan_verdict(caution_on_ours, ours)
