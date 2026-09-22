"""Reading Hugging Face's listings."""

import httpx
import pytest

from modules.llm.catalog.search import list_builds, search_models
from modules.llm.catalog.search.client import _quantization

pytestmark = pytest.mark.unit

HIT = {
    "id": "unsloth/Qwen3-8B-GGUF",
    "downloads": 412_000,
    "likes": 91,
    "lastModified": "2026-09-01T00:00:00.000Z",
    "gated": False,
    "pipeline_tag": "text-generation",
    "tags": ["gguf", "license:apache-2.0", "base_model:quantized:Qwen/Qwen3-8B"],
}
TREE = [
    {"path": "Qwen3-8B-Q4_K_M.gguf", "size": 5_027_784_512},
    {"path": "Qwen3-8B-Q8_0.gguf", "size": 8_710_000_000},
    {"path": "mmproj-F16.gguf", "size": 400_000_000},
    {"path": "Qwen3-8B-Q2_K-00001-of-00003.gguf", "size": 1_000_000},
    {"path": "README.md", "size": 900},
]


def serving(payload):
    """A Hugging Face API returning one fixed payload."""
    return httpx.MockTransport(lambda request: httpx.Response(200, json=payload))


@pytest.mark.asyncio
async def test_a_search_describes_a_repo_without_grading_it() -> None:
    """Search rows are described, not judged: no rank, ever."""
    async with httpx.AsyncClient(transport=serving([HIT])) as client:
        hits = await search_models(client, "qwen3")

    assert hits[0].repo == "unsloth/Qwen3-8B-GGUF"
    assert hits[0].downloads == 412_000
    assert not hasattr(hits[0], "rank")


@pytest.mark.asyncio
async def test_provenance_is_surfaced_because_it_is_free_and_useful() -> None:
    """It lets someone recognise an unfamiliar repo as a repackaging of a model
    they know, which is most of what a score was doing for them."""
    async with httpx.AsyncClient(transport=serving([HIT])) as client:
        hits = await search_models(client, "qwen3")

    assert hits[0].quantized_from == "Qwen/Qwen3-8B"
    assert hits[0].license == "apache-2.0"


@pytest.mark.asyncio
async def test_only_single_file_builds_are_offered() -> None:
    """A projector, a draft model and one part of a split set are not things a
    user installs on their own."""
    async with httpx.AsyncClient(transport=serving(TREE)) as client:
        builds = await list_builds(client, "unsloth/Qwen3-8B-GGUF")

    assert [b.file for b in builds] == ["Qwen3-8B-Q4_K_M.gguf", "Qwen3-8B-Q8_0.gguf"]


@pytest.mark.asyncio
async def test_builds_carry_the_quantization_out_of_their_filename() -> None:
    """Which is where uploaders put it, there being nowhere else to look."""
    async with httpx.AsyncClient(transport=serving(TREE)) as client:
        builds = await list_builds(client, "unsloth/Qwen3-8B-GGUF")

    assert [b.quantization for b in builds] == ["Q4_K_M", "Q8_0"]


@pytest.mark.parametrize(
    ("file", "expected"),
    [
        ("Qwen3-8B-Q4_K_M.gguf", "Q4_K_M"),
        ("Qwen3-8B-Q8_0.gguf", "Q8_0"),
        ("Qwen3-Coder-30B-A3B-Instruct-UD-TQ1_0.gguf", "TQ1_0"),
        ("Qwen3-Coder-30B-A3B-Instruct-UD-IQ2_XXS.gguf", "IQ2_XXS"),
        ("gemma-3-4b-it-BF16.gguf", "BF16"),
        ("SmolLM2-135M-Instruct-F16.gguf", "F16"),
        ("Qwen3-8B-UD-Q4_K_XL.gguf", "Q4_K_XL"),
    ],
)
def test_the_quantization_is_read_and_not_the_model_name(file, expected) -> None:
    """Found live: `Qwen3-Coder-...-UD-TQ1_0.gguf` parsed as "QWEN3", because a
    model name can begin with Q and contain a digit just as a quant name does.
    """
    assert _quantization(file) == expected
