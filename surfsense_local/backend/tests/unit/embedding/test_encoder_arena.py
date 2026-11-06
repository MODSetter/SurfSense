"""An embed call hands its batches' working memory back once it is done."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from modules.embedding import encoder
from modules.embedding.bundled import BGE

pytestmark = pytest.mark.unit

SHRINK = "memory.enable_memory_arena_shrinkage"


class _Session:
    def __init__(self) -> None:
        self.shrinks: list[bool] = []

    def get_inputs(self) -> list[Any]:
        return [MagicMock(name=n) for n in ("input_ids", "attention_mask")]

    def run(self, _outputs: Any, feed: dict[str, Any], options: Any = None) -> Any:
        self.shrinks.append(
            options is not None and options.get_run_config_entry(SHRINK) == "cpu:0"
        )
        rows, tokens = feed["input_ids"].shape
        return [np.ones((rows, tokens, BGE.dimension), dtype=np.float32)]


def _encoded(text: str) -> MagicMock:
    return MagicMock(ids=[1, 2, 3], attention_mask=[1, 1, 1], type_ids=[0, 0, 0])


@pytest.fixture
def session(monkeypatch: pytest.MonkeyPatch) -> _Session:
    """A stand-in model that records which runs asked to shrink."""
    fake = _Session()
    tokenizer = MagicMock()
    tokenizer.encode_batch = lambda texts: [_encoded(t) for t in texts]
    monkeypatch.setattr(encoder, "_loaded", lambda _spec, _dir: (fake, tokenizer))
    monkeypatch.setattr(encoder, "model_dir", lambda _spec: Path("."))
    return fake


def test_only_the_last_batch_of_a_call_shrinks_the_arena(session: _Session) -> None:
    """Shrinking every batch would re-grow the arena each time; never shrinking
    keeps a long document's peak for the life of the process."""
    texts = ["passage"] * (BGE.batch * 2 + 1)

    vectors = encoder.embed(BGE, texts, encoder.Purpose.DOCUMENT)

    assert len(vectors) == len(texts)
    assert session.shrinks == [False, False, True]


def test_a_call_within_one_batch_shrinks_it(session: _Session) -> None:
    """A question is one batch, and the last one of its call."""
    encoder.embed(BGE, ["question"], encoder.Purpose.QUERY)

    assert session.shrinks == [True]
