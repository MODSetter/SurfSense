"""The encoder lets go of the model files its cached sessions hold open."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.embedding import encoder
from modules.embedding.bundled import BGE

pytestmark = pytest.mark.unit


def test_releasing_drops_every_cached_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A delete that found a model file held open calls this, so the session
    holding it goes and the next embed loads its model afresh."""
    import onnxruntime
    import tokenizers

    opened: list[str] = []

    def session(path: str, **_kwargs: object) -> MagicMock:
        opened.append(path)
        return MagicMock()

    monkeypatch.setattr(onnxruntime, "InferenceSession", session)
    monkeypatch.setattr(tokenizers.Tokenizer, "from_file", lambda _path: MagicMock())
    encoder.release_sessions()

    encoder._loaded(BGE, tmp_path)
    encoder._loaded(BGE, tmp_path)
    assert len(opened) == 1
    assert encoder._loaded.cache_info().currsize == 1

    encoder.release_sessions()

    assert encoder._loaded.cache_info().currsize == 0
    encoder._loaded(BGE, tmp_path)
    assert len(opened) == 2
    encoder.release_sessions()
