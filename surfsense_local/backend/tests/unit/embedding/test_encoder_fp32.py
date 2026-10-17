"""The encoder opens the bundled bge upcast to FP32, and the file as shipped
whenever that cannot be done."""

import hashlib
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from modules.embedding import encoder
from modules.embedding.bundled import BGE
from modules.embedding.fp32_upcast import UnsupportedModelError
from modules.embedding.spec import EmbedderSpec, PinnedFile
from tests.unit.embedding import onnx_fixtures as wire

pytestmark = pytest.mark.unit


@pytest.fixture
def pinned(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[EmbedderSpec]:
    """bge's spec pinned to a tiny FP16 file, on a machine that upcasts it."""
    import tokenizers

    monkeypatch.setattr(tokenizers.Tokenizer, "from_file", lambda _path: MagicMock())
    monkeypatch.setattr(encoder, "runs_at_fp32", lambda _spec: True)
    model = wire.matmul_model(np.float16)
    (tmp_path / "model.onnx").write_bytes(model)
    sha256 = hashlib.sha256(model).hexdigest()
    encoder.release_sessions()
    yield BGE.model_copy(
        update={"weights": PinnedFile(path="model.onnx", sha256=sha256)}
    )
    encoder.release_sessions()


def _input_type(spec: EmbedderSpec, directory: Path) -> str:
    session, _tokenizer = encoder._loaded(spec, directory)
    return session.get_inputs()[0].type


def test_the_pinned_file_runs_upcast(pinned: EmbedderSpec, tmp_path: Path) -> None:
    """The session is built from the upcast bytes, not the file."""
    assert _input_type(pinned, tmp_path) == "tensor(float)"


def test_the_session_does_not_keep_the_upcast_bytes(
    pinned: EmbedderSpec, tmp_path: Path
) -> None:
    """onnxruntime's wrapper would hold all 133 MB of them for the session's life,
    in each of the three processes that embed, under whatever name it keeps them."""
    session, _tokenizer = encoder._loaded(pinned, tmp_path)

    assert session.get_inputs()[0].type == "tensor(float)"
    held = [
        name
        for name, value in vars(session).items()
        if isinstance(value, bytes | bytearray | memoryview)
    ]
    assert held == []


def test_a_failed_upcast_opens_the_file_as_shipped(
    pinned: EmbedderSpec, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Embedding still works, at FP16, rather than failing outright."""

    def refuse(_model: bytes) -> bytes:
        raise UnsupportedModelError("refused")

    monkeypatch.setattr(encoder, "upcast", refuse)

    assert _input_type(pinned, tmp_path) == "tensor(float16)"


def test_a_missing_file_fails_as_missing_not_as_a_failed_upcast(
    pinned: EmbedderSpec, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The error names the missing file; no upcast warning says otherwise."""
    (tmp_path / "model.onnx").unlink()

    with pytest.raises(Exception, match="NO_SUCHFILE"):
        encoder._loaded(pinned, tmp_path)
    assert "upcast" not in caplog.text


def test_a_file_other_than_the_pinned_one_is_not_upcast(
    pinned: EmbedderSpec, tmp_path: Path
) -> None:
    """The upcast was measured on one exact file; any other runs as it is."""
    other = pinned.model_copy(
        update={"weights": PinnedFile(path="model.onnx", sha256="0" * 64)}
    )

    assert _input_type(other, tmp_path) == "tensor(float16)"
