"""The screen's data, assembled without a network call."""

import threading
import time
from pathlib import Path

import httpx
import pytest

from modules.llm.catalog import CatalogService, load_curated_models
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


def _repo_transport(recorder: list[str], *, gguf: dict | None, header: bytes | None):
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
        return httpx.Response(200, json={"gguf": gguf} if gguf else {})

    return httpx.MockTransport(handle)


async def test_an_architecture_llama_cpp_cannot_run_costs_no_header_read(
    tmp_path, monkeypatch
) -> None:
    """The listing already said so. Reading a range out of a multi gigabyte file
    to re-learn it is bytes spent on a question that was already answered."""
    calls: list[str] = []
    transport = _repo_transport(calls, gguf={"architecture": "whisper"}, header=None)
    _serve_repo(monkeypatch, transport)
    service = CatalogService(load_curated_models(), tmp_path, tmp_path, probe=lambda _: [])

    body = await service.repo("some/whisper-gguf")

    assert body["supported"] is False
    assert "whisper" in body["ineligible_reason"]
    assert not any("/resolve/main/" in url for url in calls)


async def test_an_unsupported_repo_still_lists_what_is_in_it(
    tmp_path, monkeypatch
) -> None:
    """The screen answers "what is in here" as well as "can I run it", and an
    empty repo reads as a broken page rather than an unsupported model."""
    transport = _repo_transport([], gguf={"architecture": "whisper"}, header=None)
    _serve_repo(monkeypatch, transport)
    service = CatalogService(load_curated_models(), tmp_path, tmp_path, probe=lambda _: [])

    body = await service.repo("some/whisper-gguf")

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
    header = gguf(
        [
            kv("general.architecture", STRING, "qwen3"),
            kv("qwen3.block_count", UINT32, 36),
            kv("qwen3.attention.head_count_kv", UINT32, 8),
            kv("qwen3.attention.key_length", UINT32, 128),
            kv("qwen3.attention.value_length", UINT32, 128),
            kv("qwen3.context_length", UINT32, 40960),
            kv("qwen3.embedding_length", UINT32, 4096),
            kv("qwen3.feed_forward_length", UINT32, 12288),
            array("tokenizer.ggml.tokens", STRING, ["a", "b"]),
        ]
    )
    transport = _repo_transport([], gguf={"architecture": "qwen3"}, header=header)
    _serve_repo(monkeypatch, transport)
    service = CatalogService(load_curated_models(), tmp_path, tmp_path, probe=lambda _: [])

    body = await service.repo("unsloth/Qwen3-8B-GGUF")

    assert body["supported"] is True
    assert not any(build["fit"]["approximate"] for build in body["builds"])
