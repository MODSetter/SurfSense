"""A model used where another app keeps it runs like a downloaded one, and
removing it from SurfSense never deletes the other app's file.

Measured at b11050: a preset section whose `model` names a file outside
`--models-dir` is listed by the router and loads in place, an Ollama blob with
no `.gguf` extension included.
"""

from pathlib import Path

import pytest

from modules.llm.catalog.local.build import Build, BuildFile, FileRole
from modules.llm.catalog.local.engines.llamacpp.elsewhere.find import find_models
from modules.llm.catalog.local.engines.llamacpp.elsewhere.places import (
    App,
    Layout,
    Place,
)
from modules.llm.catalog.local.engines.llamacpp.elsewhere.record import (
    read_record,
    use_in_place,
)
from modules.llm.catalog.local.install.codes import InstallCode
from modules.llm.catalog.local.install.plan import InstallPlan, InstallRefusedError
from modules.llm.catalog.local.manifest import load_local_manifest
from modules.llm.catalog.local.rows import Origin
from modules.llm.catalog.local.service import LocalCatalogService
from modules.llm.providers.llamacpp import PRESET_FILE, LlamaCppProvider
from tests.unit.llm.catalog.local.engines.llamacpp.elsewhere.files import (
    chat_model_bytes,
    ollama_store,
    write_chat_model,
    write_projector,
)
from tests.unit.llm.providers.llamacpp.fake_router import FakeRouter

pytestmark = pytest.mark.unit


@pytest.fixture
def models_dir(tmp_path: Path) -> Path:
    """SurfSense's own models folder, empty."""
    folder = tmp_path / "models"
    folder.mkdir()
    return folder


@pytest.fixture
def service(tmp_path: Path, models_dir: Path) -> LocalCatalogService:
    """A catalog over that folder, with no other app's folders to look in."""
    return LocalCatalogService(load_local_manifest(), models_dir, tmp_path / "lib")


@pytest.fixture
def ollama_blob(tmp_path: Path, models_dir: Path) -> Path:
    """qwen3:8b pulled with Ollama, then chosen in SurfSense."""
    root = tmp_path / "ollama"
    blob, _ = ollama_store(root, "qwen3", "8b", chat_model_bytes())
    (found,) = find_models([Place(App.OLLAMA, root, Layout.OLLAMA)]).models
    use_in_place(models_dir, found)
    return blob


def test_the_preset_points_the_runtime_at_the_file_where_it_lies(
    service: LocalCatalogService, models_dir: Path, ollama_blob: Path
) -> None:
    """The preset names the other app's file, and nothing lands in the models folder."""
    service.llamacpp.reprice()

    ini = (models_dir / PRESET_FILE).read_text()
    assert "[ollama-qwen3-8b]" in ini
    assert f"model = {ollama_blob}" in ini
    assert list(models_dir.glob("*.gguf")) == []


def test_a_model_used_in_place_is_one_of_this_computers_models(
    service: LocalCatalogService, ollama_blob: Path
) -> None:
    """The catalog lists it as installed, priced, under Ollama's name for it."""
    rows = [row for row in service.catalog().rows if row.origin is Origin.ELSEWHERE]

    assert len(rows) == 1
    (row,) = rows
    assert row.name == "qwen3:8b"
    assert row.runnable
    assert row.builds[0].installed_as == "ollama-qwen3-8b"
    assert row.builds[0].fit is not None
    assert row.found_in is not None
    assert (row.found_in.app, row.found_in.path) == ("ollama", str(ollama_blob))


def test_removing_a_model_used_in_place_forgets_it_and_keeps_its_file(
    service: LocalCatalogService, models_dir: Path, ollama_blob: Path
) -> None:
    """Removal forgets the record and the preset section; the blob is untouched."""
    before = ollama_blob.read_bytes()
    service.llamacpp.reprice()

    service.remove("ollama-qwen3-8b", engine="llamacpp")

    assert ollama_blob.read_bytes() == before
    assert read_record(models_dir).models == ()
    assert "ollama-qwen3-8b" not in (models_dir / PRESET_FILE).read_text()


def test_a_model_whose_file_went_away_leaves_the_runtime_but_stays_remembered(
    service: LocalCatalogService, models_dir: Path, ollama_blob: Path
) -> None:
    """The other app deleted it, or its drive is away; it comes back with it."""
    ollama_blob.unlink()

    service.llamacpp.reprice()

    assert "ollama-qwen3-8b" not in (models_dir / PRESET_FILE).read_text()
    assert [m.model_id for m in read_record(models_dir).models] == ["ollama-qwen3-8b"]


def test_a_projector_chosen_with_the_model_loads_with_it(
    tmp_path: Path, service: LocalCatalogService, models_dir: Path
) -> None:
    """The projector paired when it was chosen is named in the preset with it."""
    snapshot = tmp_path / "hub" / "models--unsloth--Qwen3.5-4B-GGUF" / "snapshots" / "c"
    write_chat_model(
        snapshot / "Qwen3.5-4B-UD-Q4_K_XL.gguf", architecture="qwen35", embedding=2560
    )
    projector = write_projector(snapshot / "mmproj-F16.gguf", width=2560)
    (found,) = find_models(
        [Place(App.HUGGING_FACE, tmp_path / "hub", Layout.HUB_CACHE)]
    ).models
    use_in_place(models_dir, found)

    service.llamacpp.reprice()

    assert f"mmproj = {projector}" in (models_dir / PRESET_FILE).read_text()


async def test_the_runtime_types_a_model_used_in_place_by_its_own_header(
    models_dir: Path, ollama_blob: Path
) -> None:
    """The runtime adapter lists it as an installed chat model, so it can be selected."""
    router = FakeRouter(models=["ollama-qwen3-8b"])
    provider = LlamaCppProvider(
        "http://127.0.0.1:1234", models_dir, transport=router.transport()
    )

    (model,) = await provider.models()

    assert model.name == "ollama-qwen3-8b"
    assert model.installed
    assert [t.value for t in model.types] == ["text_gen"]
    assert model.known


async def test_using_a_split_whose_part_went_away_since_the_listing_is_refused(
    tmp_path: Path, service: LocalCatalogService, models_dir: Path
) -> None:
    """Read again before use: the runtime could not open a split missing a part,
    so the install ends as a gone file and nothing is recorded."""
    folder = tmp_path / "pub" / "repo"
    write_chat_model(folder / "big-Q4_K_M-00001-of-00002.gguf", split=(0, 2))
    second = write_chat_model(folder / "big-Q4_K_M-00002-of-00002.gguf", split=(1, 2))
    (found,) = find_models([Place(App.LM_STUDIO, tmp_path, Layout.TREE)]).models
    second.unlink()
    weights = BuildFile(FileRole.WEIGHTS, found.path.name, found.weights_bytes)
    plan = InstallPlan("", Build("Q4_K_M", (weights,)), "llamacpp", in_place=found)

    with pytest.raises(InstallRefusedError) as refused:
        await service.llamacpp.check(plan)

    assert refused.value.code is InstallCode.FILE_GONE
    assert read_record(models_dir).models == ()
