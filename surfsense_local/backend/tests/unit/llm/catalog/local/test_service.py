"""The local catalog service: the machine, the models folder, installs."""

import hashlib
import threading
import time
from pathlib import Path

import httpx
import pytest

from modules.llm.catalog.local import service as service_module
from modules.llm.catalog.local.engines.llamacpp.builds.in_repo import Build, BuildFile, FileRole
from modules.llm.catalog.local.installs import projector_filename, read_installs
from modules.llm.catalog.local.manifest import load_local_manifest
from modules.llm.catalog.local.rows import Origin
from modules.llm.catalog.local.service import (
    InstallPlan,
    InstallRefusedError,
    LocalCatalogService,
)
from modules.llm.fit import BadgeLevel
from modules.llm.hardware import GpuStatus
from modules.llm.providers.types import DownloadProgress
from tests.unit.llm.gguf.build import BOOL, STRING, UINT32, array, gguf, kv

pytestmark = pytest.mark.unit


@pytest.fixture
def service(tmp_path: Path) -> LocalCatalogService:
    """The shipped manifest against an empty models folder."""
    return LocalCatalogService(
        load_local_manifest(), tmp_path / "models", tmp_path / "lib"
    )


def test_the_catalog_renders_before_anything_is_installed(service) -> None:
    """The catalog renders before anything is installed."""
    catalog = service.catalog()

    curated = [r for r in catalog.local.rows if r.origin is Origin.CURATED]
    assert curated
    # A badge names a verdict exactly when it warns.
    assert all(
        bool(b.badge.verdict) == (b.badge.level is not BadgeLevel.NONE)
        for r in curated
        for b in r.builds
    )
    assert not any(b.installed_as for r in curated for b in r.builds)


def test_a_missing_runtime_does_not_stop_the_catalog(service) -> None:
    """A missing runtime does not stop the catalog."""
    catalog = service.catalog()

    assert catalog.devices == ()
    assert catalog.local.rows


def test_every_curated_build_has_a_stable_opaque_id(service) -> None:
    """Keyed per build, not by list position: row order follows fit, which moves
    with what the machine has free between two calls."""

    def ids() -> dict[tuple[str, str], str]:
        return {
            (r.id, b.build.quantization): b.catalog_id
            for r in service.catalog().local.rows
            for b in r.builds
        }

    first, second = ids(), ids()
    assert first == second
    assert len(set(first.values())) == len(first)
    assert all("/" not in t and ".gguf" not in t for t in first.values())


def test_the_machine_is_probed_once_however_many_threads_ask(tmp_path) -> None:
    """The machine is probed once however many threads ask."""
    calls = []

    def slow_probe(_):
        time.sleep(0.2)
        calls.append(1)
        return []

    service = LocalCatalogService(
        load_local_manifest(),
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
    """A broken install is never reported as a machine without a card."""

    def no_runtime(_):
        raise OSError("no staged runtime")

    service = LocalCatalogService(
        load_local_manifest(), tmp_path, tmp_path, probe=no_runtime, os_gpu=lambda: True
    )

    catalog = service.catalog()

    assert catalog.gpu_status is GpuStatus.BROKEN_INSTALL
    assert catalog.devices == ()


# installing -----------------------------------------------------------------

WEIGHTS = b"GGUF-weights"
PROJECTOR = b"GGUF-projector"


def sha(data: bytes) -> str:
    """The hex digest a manifest pins a file by."""
    return hashlib.sha256(data).hexdigest()


def vision_build() -> Build:
    """Weights and a projector that sees, pinned to one commit."""
    return Build(
        "Q4_K_M",
        (
            BuildFile(
                FileRole.WEIGHTS,
                "gemma-Q4_K_M.gguf",
                len(WEIGHTS),
                sha(WEIGHTS),
                "g/gemma-GGUF",
                "r1",
            ),
            BuildFile(
                FileRole.PROJECTOR,
                "mmproj-F16.gguf",
                len(PROJECTOR),
                sha(PROJECTOR),
                "g/gemma-GGUF",
                "r1",
                {"clip.has_vision_encoder": True},
            ),
        ),
    )


@pytest.fixture
def fake_hub(monkeypatch):
    """Serve each file's bytes to the downloader, and record the URLs asked for."""
    asked: list[str] = []

    async def download(url, destination, *, sha256=None, transport=None):
        asked.append(url)
        data = PROJECTOR if "mmproj" in url else WEIGHTS
        if sha256 is not None and sha(data) != sha256:
            raise ValueError("checksum mismatch")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        yield DownloadProgress("complete", len(data), len(data))

    monkeypatch.setattr(service_module, "download_gguf", download)
    return asked


async def test_a_build_installs_as_its_whole_file_set_pinned_and_recorded(
    service, tmp_path, fake_hub
) -> None:
    """A build installs as its whole file set pinned and recorded."""
    plan = InstallPlan("gemma-Q4_K_M", vision_build(), needs_check=False)

    steps = [step async for step in service.install(plan)]

    models = tmp_path / "models"
    assert (models / "gemma-Q4_K_M.gguf").read_bytes() == WEIGHTS
    assert (models / projector_filename("gemma-Q4_K_M")).read_bytes() == PROJECTOR
    assert all("/resolve/r1/" in url for url in fake_hub)
    assert steps[-1].completed == len(WEIGHTS) + len(PROJECTOR)
    record = read_installs(models)["gemma-Q4_K_M"]
    assert record.projector == projector_filename("gemma-Q4_K_M")
    assert record.projector_gguf["clip.has_vision_encoder"] is True


async def test_a_file_that_does_not_match_its_hash_fails_the_install(
    service, fake_hub
) -> None:
    """A file that does not match its hash fails the install."""
    bad = Build(
        "Q4_K_M",
        (BuildFile(FileRole.WEIGHTS, "x-Q4_K_M.gguf", 3, "0" * 64, "r/x", "r1"),),
    )

    with pytest.raises(ValueError):
        [
            step
            async for step in service.install(
                InstallPlan("x-Q4_K_M", bad, needs_check=False)
            )
        ]


async def test_removing_a_model_takes_its_projector_with_it(
    service, tmp_path, fake_hub
) -> None:
    """Removing a model takes its projector with it."""
    plan = InstallPlan("gemma-Q4_K_M", vision_build(), needs_check=False)
    [step async for step in service.install(plan)]

    service.remove("gemma-Q4_K_M")

    assert list((tmp_path / "models").glob("*.gguf")) == []
    assert read_installs(tmp_path / "models") == {}


def test_a_curated_id_resolves_to_its_pinned_build_without_a_check(service) -> None:
    """A curated id resolves to its pinned build without a check."""
    row = next(r for r in service.catalog().local.rows if r.id == "qwen3-8b")
    build = row.builds[0]

    plan = service.resolve_install(build.catalog_id)

    assert plan is not None
    assert plan.build == build.build
    assert not plan.needs_check
    assert service.resolve_install("never-minted") is None


def header(architecture: str = "qwen3", *, too_big: bool = False) -> bytes:
    """A chat model header, or one too big for any machine."""
    blocks = 4000 if too_big else 28
    return gguf(
        [
            kv("general.architecture", STRING, architecture),
            kv(f"{architecture}.block_count", UINT32, blocks),
            kv(f"{architecture}.embedding_length", UINT32, 1024),
            kv(f"{architecture}.attention.head_count_kv", UINT32, 8),
            kv(f"{architecture}.attention.key_length", UINT32, 128),
            kv(f"{architecture}.attention.value_length", UINT32, 128),
            kv(f"{architecture}.context_length", UINT32, 40960),
            array("tokenizer.ggml.tokens", STRING, ["a", "b"]),
        ]
    )


_REAL = httpx.AsyncClient


def serve(monkeypatch, body: bytes, projector: bytes | None = None) -> None:
    """Point every client the service opens at fixed header bytes."""

    def answer(request: httpx.Request) -> httpx.Response:
        if "mmproj" in request.url.path and projector is not None:
            return httpx.Response(206, content=projector)
        return httpx.Response(206, content=body)

    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **_: _REAL(transport=httpx.MockTransport(answer))
    )


def searched(build: Build, tag: str | None = None) -> InstallPlan:
    """A searched build that still needs its exact check."""
    return InstallPlan("m", build, needs_check=True, pipeline_tag=tag)


TEXT = Build(
    "Q4_K_M",
    (BuildFile(FileRole.WEIGHTS, "m-Q4_K_M.gguf", 1_000, "a" * 64, "r/m", "s"),),
)


async def test_a_searched_build_is_read_exactly_before_it_downloads(
    service, monkeypatch
) -> None:
    """A searched build is read exactly before it downloads."""
    serve(monkeypatch, header())

    checked = await service.check(searched(TEXT))

    assert not checked.needs_check


async def test_a_searched_build_that_cannot_chat_is_refused_before_download(
    service, monkeypatch
) -> None:
    """A searched build that cannot chat is refused before download."""
    serve(monkeypatch, header("nomic-bert"))

    with pytest.raises(InstallRefusedError, match="search"):
        await service.check(searched(TEXT))


async def test_a_searched_build_too_big_for_the_machine_is_refused(
    service, monkeypatch
) -> None:
    """A searched build too big for the machine is refused."""
    serve(monkeypatch, header(too_big=True))
    huge = Build(
        "Q4_K_M",
        (BuildFile(FileRole.WEIGHTS, "m-Q4_K_M.gguf", 10**15, "a" * 64, "r/m", "s"),),
    )

    with pytest.raises(InstallRefusedError, match="too big"):
        await service.check(searched(huge))


async def test_a_projector_that_does_not_belong_is_dropped_by_the_check(
    service, monkeypatch
) -> None:
    """A projector that does not belong is dropped by the check."""
    wrong = gguf(
        [
            kv("general.type", STRING, "mmproj"),
            kv("clip.has_vision_encoder", BOOL, True),
            kv("clip.vision.projection_dim", UINT32, 9999),
        ]
    )
    serve(monkeypatch, header(), projector=wrong)
    build = Build(
        "Q4_K_M",
        (
            *TEXT.files,
            BuildFile(FileRole.PROJECTOR, "mmproj-F16.gguf", 50, "b" * 64, "r/m", "s"),
        ),
    )

    checked = await service.check(searched(build))

    assert checked.build.projector is None
