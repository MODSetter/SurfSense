"""What the install says while a Hugging Face embedder is checked."""

from pathlib import Path

import pytest

from modules.embedding.bundled import BGE
from modules.llm.catalog.local.engines.onnxruntime import engine as engine_module
from modules.llm.catalog.local.engines.onnxruntime.engine import OnnxRuntimeEngine

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

REFUSAL = "It found 6 of 10 answers first; a search model has to find all 10."


async def test_a_pick_that_fails_its_check_ends_in_the_checks_own_words(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The check names itself with a code; its refusal carries counts and none."""
    monkeypatch.setattr(engine_module, "verify", lambda spec: (384, REFUSAL))
    engine = OnnxRuntimeEngine(tmp_path)
    engine.offer(BGE)

    steps = [step async for step in engine.after_install(BGE.id)]

    assert [(step.kind, step.code, step.message) for step in steps] == [
        ("verifying", "checking_retrieval", "Checking that it finds answers"),
        ("error", None, REFUSAL),
    ]
