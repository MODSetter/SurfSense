"""Whether a row can run here: its type, and the engine that offered it."""

import pytest

from modules.llm.catalog.local.classifier import classify
from modules.llm.catalog.local.router import row_read
from modules.llm.catalog.local.rows import LocalRow, LocalSupport, Origin
from modules.llm.catalog.local.schemas import LocalRowRead

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
    assert image.not_runnable_code is None


def test_an_image_model_found_through_llama_cpp_does_not() -> None:
    """Search reaches llama.cpp's catalog; its image hits keep saying why not."""
    image = row("sdxl", "llamacpp")

    assert not image.runnable
    assert image.not_runnable_reason == classify("sdxl").reason
    assert image.not_runnable_code == "image"


def test_a_row_no_group_refuses_says_so_under_the_fallback_code() -> None:
    """A chat model in an image engine's catalog: nothing names why, so the row
    carries the plain sentence and the code that stands for it."""
    stray = row("qwen3", "sdcpp")

    assert not stray.runnable
    assert stray.not_runnable_reason == "SurfSense cannot run this model."
    assert stray.not_runnable_code == "unsupported"


def test_a_chat_model_offered_by_llama_cpp_runs_here() -> None:
    """The case every chat row relies on."""
    assert row("qwen3", "llamacpp").runnable


def test_the_code_reaches_the_wire_beside_its_sentence() -> None:
    """What the route answers: the pair for a row that cannot run, and neither
    for one that can."""
    refused = LocalRowRead.model_validate(row_read(row("sdxl", "llamacpp"), {}))
    runs = LocalRowRead.model_validate(row_read(row("sdxl", "sdcpp"), {}))

    assert refused.not_runnable_code == "image"
    assert refused.not_runnable_reason == classify("sdxl").reason
    assert runs.not_runnable_code is None
    assert runs.not_runnable_reason is None
