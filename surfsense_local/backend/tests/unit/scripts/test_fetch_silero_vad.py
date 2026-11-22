"""The voice activity model the installer ships: from its pinned commit,
sha256-checked, with the licence MIT asks to travel with it."""

import hashlib
from dataclasses import replace

import httpx
import pytest
from fetch_silero_vad import stage

from modules.llm.transcription.voice_activity.model_file import SILERO_VAD

pytestmark = pytest.mark.unit

MODEL = b"onnx bytes"
LICENCE = b"MIT License"


def pinned_to(model: bytes, licence: bytes):
    """Silero's pin, with hashes a stub can serve."""
    return replace(
        SILERO_VAD,
        weights=replace(SILERO_VAD.weights, sha256=hashlib.sha256(model).hexdigest()),
        licence=replace(SILERO_VAD.licence, sha256=hashlib.sha256(licence).hexdigest()),
    )


def github(asked: list[str], model: bytes = MODEL) -> httpx.MockTransport:
    """GitHub serving the licence and the model, noting what was asked."""

    def answer(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        return httpx.Response(
            200, content=LICENCE if request.url.path.endswith("LICENSE") else model
        )

    return httpx.MockTransport(answer)


def test_the_model_and_its_licence_land_from_the_pinned_commit(tmp_path) -> None:
    """Under the names the app reads them by."""
    asked: list[str] = []

    stage(tmp_path, pinned_to(MODEL, LICENCE), transport=github(asked))

    base = f"https://raw.githubusercontent.com/snakers4/silero-vad/{SILERO_VAD.commit}"
    assert asked == [
        f"{base}/src/silero_vad/data/silero_vad_16k_op15.onnx",
        f"{base}/LICENSE",
    ]
    assert (tmp_path / "silero_vad_16k_op15.onnx").read_bytes() == MODEL
    assert (tmp_path / "LICENSE").read_bytes() == LICENCE


def test_a_file_that_is_not_the_pinned_one_is_refused(tmp_path) -> None:
    """An installer never ships bytes the pin did not name."""
    with pytest.raises(SystemExit, match="does not match"):
        stage(tmp_path, pinned_to(MODEL, LICENCE), transport=github([], b"other"))

    assert not (tmp_path / "silero_vad_16k_op15.onnx").exists()


def test_files_already_staged_are_not_fetched_again(tmp_path) -> None:
    """A second build reuses what the first staged."""
    pin = pinned_to(MODEL, LICENCE)
    stage(tmp_path, pin, transport=github([]))
    asked: list[str] = []

    stage(tmp_path, pin, transport=github(asked))

    assert asked == []
