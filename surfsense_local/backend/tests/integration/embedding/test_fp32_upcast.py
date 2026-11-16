"""The bundled bge upcast to FP32 keeps its vectors, on the real model."""

from pathlib import Path

import numpy as np
import pytest

from modules.embedding.bundled import BGE
from modules.embedding.encoder import Purpose, embed, release_sessions

pytestmark = pytest.mark.integration

PASSAGES = [
    "The ship sails at dawn from the northern harbour.",
    "Appropriations for the Department of Education rose by 4.2 percent, "
    "driven by special education transportation and new school openings.",
    "The Contractor shall indemnify the City against all claims arising from "
    "the performance of the Work, except those caused by the City's own "
    "negligence.",
    "## Capital Plan\n\n| Project | FY26 | FY27 |\n|---|---|---|\n"
    "| Library roof | 1.2M | 0.4M |\n| Fire station | 3.0M | 2.5M |",
]


def _vectors(monkeypatch: pytest.MonkeyPatch, precision: str) -> np.ndarray:
    monkeypatch.setenv("SURFSENSE_LOCAL_EMBED_PRECISION", precision)
    release_sessions()
    try:
        return np.array(embed(BGE, PASSAGES, Purpose.DOCUMENT))
    finally:
        release_sessions()


def test_fp32_keeps_the_fp16_vectors(
    real_model: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every library was built at FP16, so its vectors must not move. They do
    differ in the last digits, which shows the upcast really ran."""
    fp16 = _vectors(monkeypatch, "fp16")
    fp32 = _vectors(monkeypatch, "fp32")

    cosines = np.sum(fp16 * fp32, axis=1)
    assert cosines.min() >= 0.99999
    assert not np.array_equal(fp16, fp32)
