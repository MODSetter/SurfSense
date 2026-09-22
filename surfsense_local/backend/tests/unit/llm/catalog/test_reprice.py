"""Making a downloaded model reachable.

The router reads its models directory once, at startup, and reads per-model
arguments from a preset INI once, at startup. Measured: a file dropped into a
running router's directory is still invisible 26 seconds later, and appears
immediately after a restart.

So a completed download has to write the preset. That is what the Electron
watcher notices, and the restart it triggers is what surfaces the model. Without
this the file lands on disk, shows under Installed, and cannot be chatted with.
"""

from pathlib import Path

import pytest

from modules.llm.catalog import CatalogService, load_curated_models
from modules.llm.providers.llamacpp import PRESET_FILE
from tests.unit.llm.gguf.build import STRING, UINT32, array, gguf, kv

pytestmark = pytest.mark.unit


def a_model(path: Path, *, blocks: int = 28, ctx: int = 40960) -> None:
    """A parseable GGUF on disk, which is all reprice needs to price one."""
    path.write_bytes(
        gguf(
            [
                kv("general.architecture", STRING, "qwen3"),
                kv("qwen3.block_count", UINT32, blocks),
                kv("qwen3.attention.head_count_kv", UINT32, 8),
                kv("qwen3.attention.key_length", UINT32, 128),
                kv("qwen3.attention.value_length", UINT32, 128),
                kv("qwen3.context_length", UINT32, ctx),
                array("tokenizer.ggml.tokens", STRING, ["a", "b"]),
            ]
        )
    )


def a_projector(path: Path) -> None:
    """A real projector on disk, which is what the name used to stand in for.

    `reprice` now asks the header rather than the filename, so a file has to
    carry `general.type = mmproj` to be one. Every projector measured on the hub
    does.
    """
    path.write_bytes(
        gguf(
            [
                kv("general.type", STRING, "mmproj"),
                kv("general.architecture", STRING, "clip"),
            ]
        )
    )


@pytest.fixture
def service(tmp_path: Path) -> CatalogService:
    """A service over an empty models directory."""
    models = tmp_path / "models"
    models.mkdir()
    return CatalogService(load_curated_models(), models, tmp_path / "lib")


def test_a_downloaded_model_gets_a_preset_section(service, tmp_path: Path) -> None:
    """The section is what the router matches a discovered file against."""
    a_model(tmp_path / "models" / "Qwen3-1.7B-Q4_K_M.gguf")

    service.reprice()

    ini = (tmp_path / "models" / PRESET_FILE).read_text()
    assert "[Qwen3-1.7B-Q4_K_M]" in ini
    assert "ctx-size" in ini


def test_the_window_comes_from_the_fit_calculation_not_a_default(
    service, tmp_path: Path
) -> None:
    """A model trained to 8192 must not be asked for more, and llama.cpp would
    otherwise pick its own window and shrink it as far as 4096."""
    a_model(tmp_path / "models" / "small.gguf", ctx=8192)

    service.reprice()

    assert "ctx-size = 8192" in (tmp_path / "models" / PRESET_FILE).read_text()


def test_every_installed_model_is_priced_not_only_the_newest(
    service, tmp_path: Path
) -> None:
    """The file is rewritten whole, so a second install must not orphan the first."""
    a_model(tmp_path / "models" / "one.gguf")
    a_model(tmp_path / "models" / "two.gguf")

    service.reprice()

    ini = (tmp_path / "models" / PRESET_FILE).read_text()
    assert "[one]" in ini and "[two]" in ini


def test_a_partial_download_is_not_offered_to_the_runtime(
    service, tmp_path: Path
) -> None:
    """A `.part` file is a download in flight, not a model."""
    a_model(tmp_path / "models" / "done.gguf")
    (tmp_path / "models" / "busy.gguf.part").write_bytes(b"GGUF not finished")

    service.reprice()

    ini = (tmp_path / "models" / PRESET_FILE).read_text()
    assert "[done]" in ini
    assert "busy" not in ini


def test_one_unreadable_file_does_not_cost_the_others(service, tmp_path: Path) -> None:
    """A truncated or foreign file in the directory is skipped, not fatal: the
    runtime would otherwise stay dead over a file nobody asked it to load."""
    a_model(tmp_path / "models" / "good.gguf")
    (tmp_path / "models" / "corrupt.gguf").write_bytes(b"not a gguf at all")

    service.reprice()

    ini = (tmp_path / "models" / PRESET_FILE).read_text()
    assert "[good]" in ini
    assert "[corrupt]" not in ini


def test_repricing_an_empty_directory_writes_an_empty_preset(
    service, tmp_path: Path
) -> None:
    """Deleting the last model must not leave a section pointing at nothing."""
    service.reprice()

    assert (tmp_path / "models" / PRESET_FILE).read_text() == ""


def test_a_truncated_model_is_skipped_like_any_other_unreadable_one(
    service, tmp_path: Path
) -> None:
    """A file that starts with GGUF and stops early is the likelier corruption:
    an interrupted copy, or a download that bypassed the `.part` path. It failed
    differently from a file that was never a GGUF, and killed the whole preset.
    """
    a_model(tmp_path / "models" / "whole.gguf")
    (tmp_path / "models" / "cut.gguf").write_bytes(b"GGUF")

    service.reprice()

    ini = (tmp_path / "models" / PRESET_FILE).read_text()
    assert "[whole]" in ini
    assert "[cut]" not in ini


@pytest.mark.asyncio
async def test_waiting_for_the_runtime_gives_up_rather_than_hanging(
    service, tmp_path: Path
) -> None:
    """The install stream must finish even when the sidecar never restarts.

    A model the runtime cannot serve yet is a worse answer than a slow one, but
    a progress bar that never ends is worse than both.
    """
    a_model(tmp_path / "models" / "m.gguf")

    reachable = await service.wait_until_servable("m", timeout=0.3, interval=0.05)

    assert reachable is False


def test_a_projector_is_never_offered_as_a_model(tmp_path: Path) -> None:
    """Half of a vision model, not a model. It has a header and a size like any
    other file here, so without a rule it gets its own section and the user is
    offered something that cannot answer a question."""
    a_model(tmp_path / "Qwen3-VL-Q4_K_M.gguf")
    a_projector(tmp_path / "mmproj-F16.gguf")
    service = CatalogService(load_curated_models(), tmp_path, tmp_path)

    service.reprice()
    ini = (tmp_path / PRESET_FILE).read_text()

    assert "[Qwen3-VL-Q4_K_M]" in ini
    assert "[mmproj-F16]" not in ini


def test_a_vision_model_names_its_projector_and_reserves_room_for_it(
    tmp_path: Path,
) -> None:
    """`--fit` allocates the projector after it has finished placing layers and
    does not count it while deciding, so the margin has to carry its bytes."""
    a_model(tmp_path / "Qwen3-VL-Q4_K_M.gguf")
    projector = tmp_path / "mmproj-F16.gguf"
    a_projector(projector)
    padding = 600 * 1024**2 - projector.stat().st_size
    projector.write_bytes(projector.read_bytes() + b"\0" * padding)
    service = CatalogService(load_curated_models(), tmp_path, tmp_path)

    service.reprice()
    ini = (tmp_path / PRESET_FILE).read_text()

    assert f"mmproj = {projector}" in ini
    assert "fit-target = 1624" in ini


def test_a_text_model_leaves_the_margin_at_llama_cpps_own_default(
    tmp_path: Path,
) -> None:
    """One GiB, which is exactly what the badge subtracted."""
    a_model(tmp_path / "Qwen3-8B-Q4_K_M.gguf")
    service = CatalogService(load_curated_models(), tmp_path, tmp_path)

    service.reprice()

    assert "fit-target = 1024" in (tmp_path / PRESET_FILE).read_text()
