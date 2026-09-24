"""Whether a row can run here: its type, and the engine that offered it."""

import pytest

from modules.llm.catalog.local.classifier import classify
from modules.llm.catalog.local.rows import LocalRow, LocalSupport, Origin

pytestmark = pytest.mark.unit


def row(architecture: str, engine: str) -> LocalRow:
    """A row of the given architecture, as that engine's catalog would offer it."""
    return LocalRow(
        id="m",
        origin=Origin.CURATED,
        name="m",
        family="",
        classification=classify(architecture),
        support=LocalSupport(None, False, None, None),
        builds=(),
        default_quantization=None,
        recommended=False,
        engine=engine,
    )


def test_an_image_model_offered_by_sd_cpp_runs_here() -> None:
    """sd.cpp runs image models, so its own rows are runnable."""
    image = row("sdxl", "sdcpp")

    assert image.runnable
    assert image.not_runnable_reason is None


def test_an_image_model_found_through_llama_cpp_does_not() -> None:
    """Search reaches llama.cpp's catalog; its image hits keep saying why not."""
    image = row("sdxl", "llamacpp")

    assert not image.runnable
    assert image.not_runnable_reason == classify("sdxl").reason


def test_a_chat_model_offered_by_llama_cpp_runs_here() -> None:
    """The case every chat row relies on."""
    assert row("qwen3", "llamacpp").runnable
