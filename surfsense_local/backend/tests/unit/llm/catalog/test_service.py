"""The screen's data, assembled without a network call."""

import threading
import time
from pathlib import Path

import httpx
import pytest

from modules.llm.catalog import CatalogService, load_curated_models
from modules.llm.gguf.source import PROBE_BYTES
from modules.llm.hardware import GpuStatus
from tests.unit.llm.gguf.build import STRING, UINT32, array, gguf, kv

pytestmark = pytest.mark.unit


@pytest.fixture
def service(tmp_path: Path) -> CatalogService:
    """The shipped manifest against an empty models directory."""
    return CatalogService(load_curated_models(), tmp_path / "models", tmp_path / "lib")


def test_the_catalog_renders_before_anything_is_installed(service) -> None:
    """A clean machine sees badged rows on first paint, with no button to press
    and nothing downloaded."""
    catalog = service.catalog()

    assert catalog.curated
    assert all(row.badge.verdict for row in catalog.curated)
    assert catalog.installed == ()


def test_a_missing_runtime_does_not_stop_the_catalog(service) -> None:
    """Installs disable and the screen still explains itself. The library path
    here does not exist, which is what a broken or unstaged install looks like."""
    catalog = service.catalog()

    assert catalog.devices == ()
    assert catalog.curated


def test_installed_models_are_read_from_disk(tmp_path: Path) -> None:
    """The router auto-discovers the directory, so disk is the inventory."""
    models = tmp_path / "models"
    models.mkdir()
    (models / "Qwen3-8B-Q4_K_M.gguf").write_bytes(b"GGUF" + b"0" * 100)

    catalog = CatalogService(load_curated_models(), models, tmp_path / "lib").catalog()

    assert [row.model_id for row in catalog.installed] == ["Qwen3-8B-Q4_K_M"]


def test_the_recommendation_names_a_curated_model_or_nothing(service) -> None:
    """Never a searched model: recommending requires a rank, and only the
    manifest carries one."""
    catalog = service.catalog()
    ids = {row.model_id for row in catalog.curated}

    assert catalog.recommended_model_id is None or catalog.recommended_model_id in ids


def test_the_probe_runs_once_however_often_the_catalog_is_asked(service) -> None:
    """A cold probe compiles Metal shaders and costs about 19 seconds."""
    service.catalog()
    first = service.devices()

    assert service.devices() is first


def test_the_machine_is_probed_once_however_many_threads_ask(tmp_path) -> None:
    """The startup warm and a first request race for this.

    Without the lock both take the probe, which on a Mac means compiling Metal's
    shader libraries twice, concurrently, at about 19 seconds each.
    """
    calls = []

    def slow_probe(_):
        # Long enough that a second thread arriving unsynchronised would start
        # its own probe before this one has recorded a result to reuse.
        time.sleep(0.2)
        calls.append(1)
        return []

    service = CatalogService(
        load_curated_models(),
        tmp_path,
        tmp_path,
        probe=slow_probe,
        os_gpu=lambda: False,
    )

    threads = [threading.Thread(target=service.inventory) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert len(calls) == 1


def test_a_broken_install_is_never_reported_as_a_machine_without_a_card(
    tmp_path,
) -> None:
    """Phase 8.3's rule, at the seam the screen actually reads."""

    def no_runtime(_):
        raise OSError("no staged runtime")

    service = CatalogService(
        load_curated_models(), tmp_path, tmp_path, probe=no_runtime, os_gpu=lambda: True
    )

    catalog = service.catalog()

    assert catalog.gpu_status is GpuStatus.BROKEN_INSTALL
    assert catalog.devices == ()


def gguf_bytes(*, architecture: str = "qwen3") -> bytes:
    """A header a repo read can parse, for whatever architecture a test needs."""
    return gguf(
        [
            kv("general.architecture", STRING, architecture),
            kv(f"{architecture}.block_count", UINT32, 36),
            kv(f"{architecture}.attention.head_count_kv", UINT32, 8),
            kv(f"{architecture}.attention.key_length", UINT32, 128),
            kv(f"{architecture}.attention.value_length", UINT32, 128),
            kv(f"{architecture}.context_length", UINT32, 40960),
            kv(f"{architecture}.embedding_length", UINT32, 4096),
            kv(f"{architecture}.feed_forward_length", UINT32, 12288),
            array("tokenizer.ggml.tokens", STRING, ["a", "b"]),
        ]
    )


_REAL_ASYNC_CLIENT = httpx.AsyncClient


def _serve_repo(monkeypatch, transport: httpx.MockTransport) -> None:
    """Point every client the service opens at a transport.

    The real class is captured at import, because replacing the name with a
    lambda that then calls the name is a recursion rather than a fake.
    """
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: _REAL_ASYNC_CLIENT(transport=transport),
    )


def _repo_transport(
    recorder: list[str],
    *,
    gguf: dict | None,
    header: bytes | None,
    tag: str | None = None,
):
    """Answers the three calls `repo()` makes, and records which were made."""

    def handle(request: httpx.Request) -> httpx.Response:
        recorder.append(str(request.url))
        if "/tree/main" in request.url.path:
            return httpx.Response(
                200,
                json=[
                    {"path": "model-Q4_K_M.gguf", "size": 5_000_000_000},
                    {"path": "model-Q8_0.gguf", "size": 8_000_000_000},
                ],
            )
        if "/resolve/main/" in request.url.path:
            if header is None:
                return httpx.Response(500)
            return httpx.Response(200, content=header)
        listing: dict = {"gguf": gguf} if gguf else {}
        if tag is not None:
            listing["pipeline_tag"] = tag
        return httpx.Response(200, json=listing)

    return httpx.MockTransport(handle)


async def test_a_refusal_is_made_from_the_file_and_costs_only_the_probe(
    tmp_path, monkeypatch
) -> None:
    """A refusal used to be free and was wrong 17 times per 1000 repos.

    It now reads the candidate build, and reads it cheaply: a file that is not a
    chat model carries no tokenizer, so its header ends within the probe and the
    widening steps are never asked for. Being right costs a quarter of a
    megabyte, once, on a repo nobody was going to install.
    """
    ranges: list[str] = []

    def handle(request):
        if "/tree/main" in request.url.path:
            return httpx.Response(
                200, json=[{"path": "model-Q4_K_M.gguf", "size": 5_000_000_000}]
            )
        if "/resolve/main/" in request.url.path:
            ranges.append(request.headers["Range"])
            return httpx.Response(206, content=gguf_bytes(architecture="nomic-bert"))
        return httpx.Response(200, json={"gguf": {"architecture": "nomic-bert"}})

    _serve_repo(monkeypatch, httpx.MockTransport(handle))
    service = CatalogService(load_curated_models(), tmp_path, tmp_path, probe=lambda _: [])

    body = await service.repo("some/embed-gguf")

    assert body["supported"] is False
    # The wording itself is `not_chat.refusal`'s contract and is asserted there;
    # a repo refused without one would leave a blank row on the screen.
    assert body["ineligible_reason"]
    assert ranges == [f"bytes=0-{PROBE_BYTES - 1}"]


async def test_an_unsupported_repo_still_lists_what_is_in_it(
    tmp_path, monkeypatch
) -> None:
    """The screen answers "what is in here" as well as "can I run it", and an
    empty repo reads as a broken page rather than an unsupported model."""
    transport = _repo_transport(
        [], gguf=None, header=gguf_bytes(architecture="nomic-bert")
    )
    _serve_repo(monkeypatch, transport)
    service = CatalogService(load_curated_models(), tmp_path, tmp_path, probe=lambda _: [])

    body = await service.repo("some/embed-gguf")

    assert len(body["builds"]) == 2
    assert all(not build["can_install"] for build in body["builds"])


async def test_a_header_that_cannot_be_read_prices_from_size_and_says_so(
    tmp_path, monkeypatch
) -> None:
    """Refusing the whole repo over one unreadable header would hide builds the
    user can run. The size alone still orders the ladder, and `approximate` is
    what lets the screen show that the number is a rough one."""
    transport = _repo_transport([], gguf={"architecture": "qwen3"}, header=None)
    _serve_repo(monkeypatch, transport)
    service = CatalogService(load_curated_models(), tmp_path, tmp_path, probe=lambda _: [])

    body = await service.repo("unsloth/Qwen3-8B-GGUF")

    assert body["builds"]
    assert all(build["fit"]["approximate"] for build in body["builds"])


async def test_a_readable_header_is_never_called_approximate(
    tmp_path, monkeypatch
) -> None:
    """The flag means "priced from the file size alone", so a real read must
    clear it or the screen hedges a number it did not need to hedge."""
    transport = _repo_transport(
        [], gguf={"architecture": "qwen3"}, header=gguf_bytes()
    )
    _serve_repo(monkeypatch, transport)
    service = CatalogService(load_curated_models(), tmp_path, tmp_path, probe=lambda _: [])

    body = await service.repo("unsloth/Qwen3-8B-GGUF")

    assert body["supported"] is True
    assert not any(build["fit"]["approximate"] for build in body["builds"])


async def test_a_model_wearing_a_chat_architecture_is_refused_by_its_tag(
    tmp_path, monkeypatch
) -> None:
    """The hole the header gate cannot see.

    Measured across the 500 most downloaded GGUF repos: `Nemotron-3-Embed-8B`
    declares `mistral3`, which llama.cpp builds and `NOT_CHAT` has no reason to
    refuse, so it installs as though it were a chat model. Its repo tag says
    `sentence-similarity`, and that is the only thing that knows.
    """
    transport = _repo_transport(
        [],
        gguf={"architecture": "mistral3"},
        header=gguf_bytes(architecture="mistral3"),
        tag="sentence-similarity",
    )
    _serve_repo(monkeypatch, transport)
    service = CatalogService(load_curated_models(), tmp_path, tmp_path, probe=lambda _: [])

    body = await service.repo("nvidia/Nemotron-3-Embed-8B-GGUF")

    assert body["supported"] is False
    assert "search" in body["ineligible_reason"].lower()


async def test_an_untagged_repo_is_priced_normally(tmp_path, monkeypatch) -> None:
    """Four fifths of GGUF repos carry no tag. Treating a missing tag as a
    refusal would empty the search screen, which is why this is a denylist."""
    transport = _repo_transport([], gguf={"architecture": "qwen3"}, header=None, tag=None)
    _serve_repo(monkeypatch, transport)
    service = CatalogService(load_curated_models(), tmp_path, tmp_path, probe=lambda _: [])

    body = await service.repo("some/qwen3-gguf")

    assert body["supported"] is True
    assert body["builds"]


async def test_a_vision_chat_model_is_not_refused_by_its_tag(
    tmp_path, monkeypatch
) -> None:
    """`image-text-to-text` is how a multimodal chat model is tagged. Reading it
    as a picture model would turn away the whole vision family."""
    transport = _repo_transport(
        [], gguf={"architecture": "qwen3vl"}, header=None, tag="image-text-to-text"
    )
    _serve_repo(monkeypatch, transport)
    service = CatalogService(load_curated_models(), tmp_path, tmp_path, probe=lambda _: [])

    body = await service.repo("some/qwen3-vl-gguf")

    assert body["supported"] is True


async def test_a_vision_repo_is_judged_by_its_model_not_its_sidecar(
    tmp_path, monkeypatch
) -> None:
    """The measured defect this replaces.

    Hugging Face parses one GGUF per repo and serves that as the repo's answer.
    `Jackrong/Qwen3.8-27B-MTP-GGUF` holds twelve builds of a Qwen 3.5 chat model
    beside one vision sidecar; Hugging Face read the sidecar and reported the
    repo as `clip`. 17 of the 1000 most downloaded repos are refused this way,
    13 of them vision models, and the refusal tells the reader to install the
    model it belongs to, which is that repo.

    `list_builds` already excludes the sidecar, so the candidate build's own
    header is the answer and we already fetch it.
    """
    header = gguf_bytes(architecture="qwen35")
    transport = _repo_transport(
        [],
        gguf={"architecture": "clip"},
        header=header,
        tag="image-text-to-text",
    )
    _serve_repo(monkeypatch, transport)
    service = CatalogService(load_curated_models(), tmp_path, tmp_path, probe=lambda _: [])

    body = await service.repo("Jackrong/Qwen3.8-27B-MTP-GGUF")

    assert body["supported"] is True
    assert body["architecture"] == "qwen35"
    assert len(body["builds"]) == 2


async def test_a_repo_whose_model_really_cannot_chat_is_still_refused(
    tmp_path, monkeypatch
) -> None:
    """The other half: the header is now the authority in both directions, so a
    real embedding repo is refused on its own bytes rather than on a summary."""
    header = gguf_bytes(architecture="nomic-bert")
    transport = _repo_transport(
        [], gguf={"architecture": "nomic-bert"}, header=header, tag=None
    )
    _serve_repo(monkeypatch, transport)
    service = CatalogService(load_curated_models(), tmp_path, tmp_path, probe=lambda _: [])

    body = await service.repo("nomic-ai/some-embed-gguf")

    assert body["supported"] is False
    assert "search" in body["ineligible_reason"].lower()


async def test_a_sidecar_sorting_first_does_not_refuse_the_whole_repo(
    tmp_path, monkeypatch
) -> None:
    """The last place a filename still decided something.

    `list_builds` orders by size and a draft head is always smaller than the
    model it accelerates, so in a repo shipping both, the head is `builds[0]`.
    Judging it would refuse every build of a working model, which is the same
    failure Hugging Face's repo summary used to cause, from our own ordering
    instead.

    The file says what it is, so the walk moves on rather than believing the
    order it was handed.
    """
    served = {
        "Qwen3-Q8_0-MTP.gguf": gguf_bytes(architecture="eagle3"),
        "model-Q4_K_M.gguf": gguf_bytes(architecture="qwen3"),
    }

    def handle(request: httpx.Request) -> httpx.Response:
        if "/tree/main" in request.url.path:
            return httpx.Response(
                200,
                json=[
                    {"path": "MTP/Qwen3-Q8_0-MTP.gguf", "size": 1_000_000_000},
                    {"path": "model-Q4_K_M.gguf", "size": 5_000_000_000},
                ],
            )
        if "/resolve/main/" in request.url.path:
            name = request.url.path.rsplit("/", 1)[-1]
            return httpx.Response(206, content=served[name])
        return httpx.Response(200, json={"gguf": {"architecture": "qwen3"}})

    _serve_repo(monkeypatch, httpx.MockTransport(handle))
    service = CatalogService(load_curated_models(), tmp_path, tmp_path, probe=lambda _: [])

    body = await service.repo("some/qwen3-with-a-drafter")

    assert body["supported"] is True
    assert body["architecture"] == "qwen3"


async def test_a_repo_of_nothing_but_sidecars_is_still_refused(
    tmp_path, monkeypatch
) -> None:
    """The walk admits nothing on its own. A repo that never yields a model is
    described by the last thing it did yield, not quietly let through."""
    def handle(request: httpx.Request) -> httpx.Response:
        if "/tree/main" in request.url.path:
            return httpx.Response(
                200, json=[{"path": "MTP/Qwen3-Q8_0-MTP.gguf", "size": 1_000_000_000}]
            )
        if "/resolve/main/" in request.url.path:
            return httpx.Response(206, content=gguf_bytes(architecture="eagle3"))
        return httpx.Response(200, json={})

    _serve_repo(monkeypatch, httpx.MockTransport(handle))
    service = CatalogService(load_curated_models(), tmp_path, tmp_path, probe=lambda _: [])

    body = await service.repo("some/drafters-only")

    assert body["supported"] is False


def test_a_projector_named_anything_is_not_offered_as_a_model(tmp_path) -> None:
    """The last filename guess on the local side.

    `reprice` reads every header anyway, to price the model, so checking the
    name first only saved a read it was about to do. Reading first and asking
    the file makes it right for a publisher who did not follow the convention,
    and `general.type = mmproj` is what every projector measured on the hub
    actually carries.
    """
    models = tmp_path / "models"
    models.mkdir()
    (models / "vision-half-BF16.gguf").write_bytes(
        gguf([kv("general.type", STRING, "mmproj"),
              kv("general.architecture", STRING, "clip")])
    )
    (models / "Qwen3-8B-Q4_K_M.gguf").write_bytes(gguf_bytes())
    service = CatalogService(load_curated_models(), models, tmp_path, probe=lambda _: [])

    service.reprice()

    written = (models / "models.ini").read_text()
    assert "vision-half-BF16" not in written
    assert "Qwen3-8B-Q4_K_M" in written
