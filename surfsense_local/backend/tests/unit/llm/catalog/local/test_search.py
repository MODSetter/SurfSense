"""Search: a repo opens from its listing alone, and one build is read exactly
before it downloads."""

import httpx
import pytest

from modules.llm.catalog.local.builds import BuildFile, FileRole
from modules.llm.catalog.local.rows import Origin
from modules.llm.catalog.local.search.exact_check import check_build
from modules.llm.catalog.local.search.hits import search_models
from modules.llm.catalog.local.search.listing import read_listing
from modules.llm.catalog.local.search.repo_row import repo_row
from modules.llm.catalog.local.search.tickets import TicketStore
from modules.llm.fit import FitState, HardwareBudget
from modules.llm.model_type import ModelType
from tests.unit.llm.gguf.build import BOOL, STRING, UINT32, array, gguf, kv

pytestmark = pytest.mark.unit

MIB = 1024**2
BUDGET = HardwareBudget(23000 * MIB, 24576 * MIB, 1024 * MIB, 32000 * MIB, False, True)
REPO = "unsloth/gemma-4-E4B-it-GGUF"
SHA = "bfc15c382204943c3a8fff0c750b94ae2364d7a3"
INFO = {
    "id": REPO,
    "sha": SHA,
    "pipeline_tag": "image-text-to-text",
    "gated": False,
    "gguf": {"architecture": "clip"},
}
TREE = [
    {
        "type": "file",
        "path": "gemma-4-E4B-it-Q4_K_M.gguf",
        "size": 4_977_171_584,
        "lfs": {"oid": "85" * 32},
    },
    {
        "type": "file",
        "path": "gemma-4-E4B-it-Q8_0.gguf",
        "size": 8_000_000_000,
        "lfs": {"oid": "86" * 32},
    },
    {
        "type": "file",
        "path": "mmproj-F16.gguf",
        "size": 990_372_672,
        "lfs": {"oid": "dd" * 32},
    },
    {"type": "file", "path": "imatrix_unsloth.gguf_file", "size": 4_429_024},
    {"type": "file", "path": "README.md", "size": 900},
]


def hub(requests: list[httpx.Request]) -> httpx.MockTransport:
    """A Hugging Face API that records what it was asked."""

    def answer(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/tree/main"):
            return httpx.Response(200, json=TREE)
        if request.url.path == f"/api/models/{REPO}":
            return httpx.Response(200, json=INFO)
        return httpx.Response(404)

    return httpx.MockTransport(answer)


async def listing():
    """One repo's listing, and the requests it cost."""
    requests: list[httpx.Request] = []
    async with httpx.AsyncClient(transport=hub(requests)) as client:
        return await read_listing(client, REPO), requests


@pytest.mark.asyncio
async def test_opening_a_repo_reads_its_listing_and_no_file() -> None:
    """Opening a repo reads its listing and no file."""
    found, requests = await listing()

    assert len(requests) == 2
    assert not any("resolve" in str(r.url) or "Range" in r.headers for r in requests)
    assert found.revision == SHA


@pytest.mark.asyncio
async def test_a_searched_repo_is_the_same_row_shape_with_nothing_recommended() -> None:
    """A searched repo is the same row shape with nothing recommended."""
    found, _ = await listing()
    store = TicketStore()

    row = repo_row(found, BUDGET, store.mint)

    assert row.origin is Origin.SEARCH
    assert row.default_quantization is None
    assert not row.recommended
    assert not any(b.recommended for b in row.builds)
    assert [b.build.quantization for b in row.builds] == ["Q4_K_M", "Q8_0"]


@pytest.mark.asyncio
async def test_listing_pricing_is_an_estimate_that_counts_the_projector() -> None:
    """Listing pricing is an estimate that counts the projector."""
    found, _ = await listing()

    row = repo_row(found, BUDGET, TicketStore().mint)

    q4 = row.builds[0]
    assert q4.fit.approximate
    assert q4.build.footprint_bytes == 4_977_171_584 + 990_372_672
    assert q4.fit.need_bytes > q4.build.footprint_bytes


@pytest.mark.asyncio
async def test_a_projector_found_by_name_reads_images_until_its_header_says_otherwise() -> (
    None
):
    """A projector found by name reads images until its header says otherwise."""
    found, _ = await listing()

    row = repo_row(found, BUDGET, TicketStore().mint)

    assert row.support.reads_images
    assert all(b.reads_images and not b.projector_checked for b in row.builds)


@pytest.mark.asyncio
async def test_a_projector_summary_is_not_taken_as_the_repos_model() -> None:
    """Hugging Face parsed the sidecar and called the repo `clip`."""
    found, _ = await listing()

    row = repo_row(found, BUDGET, TicketStore().mint)

    assert row.classification.types == (ModelType.TEXT_GEN,)
    assert row.classification.approximate
    assert all(b.can_install for b in row.builds)


@pytest.mark.asyncio
async def test_a_repo_that_is_not_a_chat_model_lists_its_builds_but_offers_none() -> (
    None
):
    """A repo that is not a chat model lists its builds but offers none."""
    found, _ = await listing()
    embedder = type(found)(**{**found.__dict__, "pipeline_tag": "sentence-similarity"})

    row = repo_row(embedder, BUDGET, TicketStore().mint)

    assert row.builds
    assert not row.runnable
    assert not any(b.can_install for b in row.builds)


def model_header(embedding: int = 2560) -> bytes:
    """A model header of a given width."""
    return gguf(
        [
            kv("general.architecture", STRING, "gemma3"),
            kv("gemma3.block_count", UINT32, 34),
            kv("gemma3.embedding_length", UINT32, embedding),
            kv("gemma3.attention.head_count_kv", UINT32, 4),
            kv("gemma3.attention.key_length", UINT32, 256),
            kv("gemma3.attention.value_length", UINT32, 256),
            kv("gemma3.context_length", UINT32, 131072),
            array("tokenizer.ggml.tokens", STRING, ["a", "b"]),
        ]
    )


def projector_header(width: int) -> bytes:
    """A projector header of a given width."""
    return gguf(
        [
            kv("general.type", STRING, "mmproj"),
            kv("clip.has_vision_encoder", BOOL, True),
            kv("clip.vision.projection_dim", UINT32, width),
        ]
    )


def files(projector_width: int):
    """A hub serving a model header, or a projector's for a projector path."""

    def answer(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        body = projector_header(projector_width) if "mmproj" in path else model_header()
        return httpx.Response(206, content=body)

    return httpx.MockTransport(answer)


BUILD_FILES = (
    BuildFile(
        FileRole.WEIGHTS,
        "gemma-4-E4B-it-Q4_K_M.gguf",
        4_977_171_584,
        "85" * 32,
        REPO,
        SHA,
    ),
    BuildFile(FileRole.PROJECTOR, "mmproj-F16.gguf", 990_372_672, "dd" * 32, REPO, SHA),
)


@pytest.mark.asyncio
async def test_the_exact_check_reads_the_build_and_its_projector() -> None:
    """The exact check reads the build and its projector."""
    from modules.llm.catalog.local.builds import Build

    async with httpx.AsyncClient(transport=files(2560)) as client:
        checked = await check_build(
            client, Build("Q4_K_M", BUILD_FILES), "image-text-to-text", BUDGET
        )

    assert checked.is_model
    assert checked.reads_images
    assert not checked.fit.approximate
    assert checked.fit.state is FitState.FITS
    assert checked.build.projector is not None
    assert checked.build.projector.gguf["clip.has_vision_encoder"] is True


@pytest.mark.asyncio
async def test_a_projector_for_another_model_is_dropped_before_download() -> None:
    """A projector for another model is dropped before download."""
    from modules.llm.catalog.local.builds import Build

    async with httpx.AsyncClient(transport=files(4096)) as client:
        checked = await check_build(client, Build("Q4_K_M", BUILD_FILES), None, BUDGET)

    assert not checked.reads_images
    assert checked.build.projector is None


@pytest.mark.asyncio
async def test_a_search_describes_a_repo_without_grading_it() -> None:
    """A search describes a repo without grading it."""
    hit = {
        "id": REPO,
        "downloads": 412_000,
        "likes": 91,
        "gated": False,
        "tags": ["gguf", "license:gemma", "base_model:quantized:google/gemma-4-E4B-it"],
    }
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=[hit]))
    ) as client:
        (found,) = await search_models(client, "gemma")

    assert found.quantized_from == "google/gemma-4-E4B-it"
    assert found.license == "gemma"
    assert not hasattr(found, "rank")


def test_a_ticket_resolves_to_the_build_it_was_minted_for() -> None:
    """A ticket resolves to the build it was minted for."""
    from modules.llm.catalog.local.builds import Build

    store = TicketStore(ttl_seconds=300)
    build = Build("Q4_K_M", BUILD_FILES)
    token = store.mint(build, pipeline_tag="image-text-to-text", now=0.0)

    ticket = store.resolve(token, now=1.0)
    assert ticket is not None and ticket.build == build
    assert store.resolve(token, now=301.0) is None
    assert store.resolve("never-minted") is None
