"""The manifest and the models folder, as the screen's local rows.

The badge has to describe the load the app performs, on every machine shape the
app can produce, and a recommended build never spills more than a little.
"""

from pathlib import Path

import pytest

from modules.llm.catalog.local.catalog import local_catalog
from modules.llm.catalog.local.downloaded import scan
from modules.llm.catalog.local.installs import InstalledBuild, projector_filename
from modules.llm.catalog.local.manifest import load_local_manifest
from modules.llm.catalog.local.rows import Origin
from modules.llm.fit import BadgeLevel, HardwareBudget, SpeedTier, plan_load, speed_tier
from modules.llm.model_type import ModelType
from tests.unit.llm.gguf.build import BOOL, STRING, UINT32, array, gguf, kv

pytestmark = pytest.mark.unit

MIB = 1024**2
BUDGETS = {
    "discrete-6gb": HardwareBudget(
        5234 * MIB, 6002 * MIB, 1024 * MIB, 22750 * MIB, False, True
    ),
    "discrete-24gb": HardwareBudget(
        23000 * MIB, 24576 * MIB, 1024 * MIB, 32000 * MIB, False, True
    ),
    "unified-8gb": HardwareBudget(
        5222 * MIB, 5461 * MIB, 1024 * MIB, 6144 * MIB, True, True
    ),
    "unified-16gb": HardwareBudget(
        10922 * MIB, 11468 * MIB, 1024 * MIB, 14336 * MIB, True, True
    ),
    "no-gpu-16gb": HardwareBudget(0, 0, 1024 * MIB, 14 * 1024 * MIB, False, False),
    "no-gpu-4gb": HardwareBudget(0, 0, 1024 * MIB, 3 * 1024 * MIB, False, False),
}
CURATED = load_local_manifest().models


def catalog(budget, downloaded=()):
    """The shipped manifest against a budget and whatever is on disk."""
    return local_catalog(
        CURATED, list(downloaded), budget, lambda b: f"id:{b.quantization}"
    )


def curated_rows(budget):
    """Only the rows the manifest names."""
    return [row for row in catalog(budget).rows if row.origin is Origin.CURATED]


@pytest.mark.parametrize("budget_name", BUDGETS)
def test_every_build_is_badged_as_it_will_be_loaded(budget_name) -> None:
    """Every build is badged as it will be loaded."""
    budget = BUDGETS[budget_name]
    shapes = {model.id: model.model_shape for model in CURATED}

    for row in curated_rows(budget):
        for build in row.builds:
            projector = build.build.projector
            plan = plan_load(
                shapes[row.id],
                build.build.weights_bytes,
                budget,
                mmproj_bytes=projector.size_bytes if projector else 0,
            )
            assert build.fit.state is plan.verdict.state, (
                row.id,
                build.build.quantization,
            )


@pytest.mark.parametrize("budget_name", BUDGETS)
def test_a_recommended_build_never_runs_slowly(budget_name) -> None:
    """A recommended build never runs slowly."""
    for row in curated_rows(BUDGETS[budget_name]):
        for build in row.builds:
            if build.recommended:
                assert speed_tier(build.fit) in {SpeedTier.FULL, SpeedTier.LIGHT_SPILL}
                assert build.badge.level is BadgeLevel.NONE


@pytest.mark.parametrize("budget_name", BUDGETS)
def test_each_model_recommends_one_build_at_most_and_never_above_its_default(
    budget_name,
) -> None:
    """Each model recommends one build at most and never above its default."""
    for row in curated_rows(BUDGETS[budget_name]):
        picked = [b for b in row.builds if b.recommended]
        assert len(picked) <= 1
        if picked:
            default = next(
                b
                for b in row.builds
                if b.build.quantization == row.default_quantization
            )
            assert picked[0].build.footprint_bytes <= default.build.footprint_bytes


def test_a_roomy_machine_gets_the_default_build_not_the_largest() -> None:
    """A roomy machine gets the default build not the largest."""
    row = next(r for r in curated_rows(BUDGETS["discrete-24gb"]) if r.id == "qwen3-8b")

    (picked,) = [b for b in row.builds if b.recommended]
    assert picked.build.quantization == row.default_quantization == "UD-Q4_K_XL"


def test_a_tight_machine_steps_down_a_build_before_a_model() -> None:
    """The preferred model at a smaller build before a smaller model."""
    result = catalog(BUDGETS["unified-16gb"])
    star = next(r for r in result.rows if r.id == result.recommended_id)

    (picked,) = [b for b in star.builds if b.recommended]
    assert star.id in {"qwen3-14b", "qwen3-32b"}
    assert (
        picked.build.quantization != star.default_quantization or star.id == "qwen3-14b"
    )


def test_one_model_is_starred_and_it_is_curated() -> None:
    """One model is starred and it is curated."""
    result = catalog(BUDGETS["unified-8gb"])

    starred = [row for row in result.rows if row.recommended]
    assert len(starred) == 1
    assert starred[0].origin is Origin.CURATED
    assert starred[0].id == result.recommended_id


def test_a_machine_that_can_run_nothing_well_stars_nothing() -> None:
    """A machine that can run nothing well stars nothing."""
    tiny = HardwareBudget(0, 0, 64 * MIB, 128 * MIB, False, False)

    assert catalog(tiny).recommended_id is None


def test_no_row_carries_a_score() -> None:
    """No row carries a score."""
    row = curated_rows(BUDGETS["unified-8gb"])[0]

    for field in ("score", "rank", "position", "quality"):
        assert not hasattr(row, field)


# downloaded files ---------------------------------------------------------


def a_model(path: Path, architecture: str = "qwen3", embedding: int = 1024) -> None:
    """A parseable chat model header on disk."""
    path.write_bytes(
        gguf(
            [
                kv("general.architecture", STRING, architecture),
                kv(f"{architecture}.block_count", UINT32, 28),
                kv(f"{architecture}.embedding_length", UINT32, embedding),
                kv(f"{architecture}.attention.head_count_kv", UINT32, 8),
                kv(f"{architecture}.attention.key_length", UINT32, 128),
                kv(f"{architecture}.attention.value_length", UINT32, 128),
                kv(f"{architecture}.context_length", UINT32, 40960),
                array("tokenizer.ggml.tokens", STRING, ["a", "b"]),
            ]
        )
    )


def a_projector(path: Path, width: int = 1024) -> None:
    """A vision projector header on disk."""
    path.write_bytes(
        gguf(
            [
                kv("general.type", STRING, "mmproj"),
                kv("general.architecture", STRING, "clip"),
                kv("clip.has_vision_encoder", BOOL, True),
                kv("clip.vision.projection_dim", UINT32, width),
            ]
        )
    )


def test_a_curated_build_on_disk_shows_as_its_curated_row(tmp_path: Path) -> None:
    """A curated build on disk shows as its curated row."""
    a_model(tmp_path / "Qwen3-8B-Q4_K_M.gguf")

    result = catalog(BUDGETS["discrete-24gb"], scan(tmp_path, {}))

    row = next(r for r in result.rows if r.id == "qwen3-8b")
    installed = [b for b in row.builds if b.installed_as]
    assert [b.build.quantization for b in installed] == ["Q4_K_M"]
    assert all(r.origin is Origin.CURATED for r in result.rows)


def test_a_curated_model_downloaded_from_an_alias_repo_is_recognised(
    tmp_path: Path,
) -> None:
    """A curated model downloaded from an alias repo is recognised."""
    a_model(tmp_path / "Qwen_Qwen3-8B-Q4_K_M.gguf")
    record = InstalledBuild(
        "Qwen_Qwen3-8B-Q4_K_M",
        "bartowski/Qwen_Qwen3-8B-GGUF",
        "r",
        "Q4_K_M",
        ("Qwen_Qwen3-8B-Q4_K_M.gguf",),
    )

    result = catalog(
        BUDGETS["discrete-24gb"], scan(tmp_path, {record.model_id: record})
    )

    row = next(r for r in result.rows if r.id == "qwen3-8b")
    assert [b.installed_as for b in row.builds if b.installed_as] == [
        "Qwen_Qwen3-8B-Q4_K_M"
    ]


def test_any_other_file_is_its_own_row_judged_by_its_header(tmp_path: Path) -> None:
    """Any other file is its own row judged by its header."""
    a_model(tmp_path / "mystery-Q5_K_M.gguf")
    a_model(tmp_path / "embedder.gguf", architecture="nomic-bert")

    rows = {r.id: r for r in catalog(BUDGETS["discrete-24gb"], scan(tmp_path, {})).rows}

    assert rows["mystery-Q5_K_M"].origin is Origin.DOWNLOADED
    assert rows["mystery-Q5_K_M"].classification.types == (ModelType.TEXT_GEN,)
    assert rows["mystery-Q5_K_M"].builds[0].build.quantization == "Q5_K_M"
    assert not rows["embedder"].runnable
    assert rows["embedder"].not_runnable_reason


def test_a_projector_is_never_a_row_of_its_own(tmp_path: Path) -> None:
    """A projector is never a row of its own."""
    a_model(tmp_path / "vision.gguf")
    a_projector(tmp_path / "mmproj-F16.gguf")

    ids = {
        r.id
        for r in catalog(BUDGETS["discrete-24gb"], scan(tmp_path, {})).rows
        if r.origin is Origin.DOWNLOADED
    }

    assert ids == {"vision"}


def test_a_lone_projector_is_never_guessed_onto_a_model(tmp_path: Path) -> None:
    """A text model beside some other model's projector does not read images."""
    a_model(tmp_path / "text-only.gguf")
    a_projector(tmp_path / "mmproj-F16.gguf")

    (row,) = [
        r
        for r in catalog(BUDGETS["discrete-24gb"], scan(tmp_path, {})).rows
        if r.origin is Origin.DOWNLOADED
    ]

    assert not row.support.reads_images


def test_a_projector_saved_under_the_models_name_reads_images_and_is_priced(
    tmp_path: Path,
) -> None:
    """A projector saved under the models name reads images and is priced."""
    a_model(tmp_path / "vision.gguf")
    a_projector(tmp_path / projector_filename("vision"))

    (row,) = [
        r
        for r in catalog(BUDGETS["discrete-24gb"], scan(tmp_path, {})).rows
        if r.origin is Origin.DOWNLOADED
    ]

    assert row.support.reads_images
    assert row.builds[0].build.projector is not None
    assert row.builds[0].reads_images


def test_a_projector_of_the_wrong_width_does_not_read_images(tmp_path: Path) -> None:
    """A projector of the wrong width does not read images."""
    a_model(tmp_path / "vision.gguf", embedding=1024)
    a_projector(tmp_path / projector_filename("vision"), width=4096)

    (row,) = [
        r
        for r in catalog(BUDGETS["discrete-24gb"], scan(tmp_path, {})).rows
        if r.origin is Origin.DOWNLOADED
    ]

    assert not row.support.reads_images


def test_an_unreadable_file_is_listed_as_an_approximate_chat_model(
    tmp_path: Path,
) -> None:
    """Refusing on a failed read hides a model the user may be able to run."""
    (tmp_path / "cut.gguf").write_bytes(b"GGUF")

    (row,) = [
        r
        for r in catalog(BUDGETS["discrete-24gb"], scan(tmp_path, {})).rows
        if r.origin is Origin.DOWNLOADED
    ]

    assert row.runnable
    assert row.classification.approximate
    assert row.builds[0].fit.approximate


def test_an_eight_gigabyte_mac_stars_a_four_bit_build_not_a_three_bit_larger_one() -> (
    None
):
    """The measured screenshot: the star sat on Qwen3 8B at UD-Q3_K_XL beside
    Qwen3 4B running at full speed. Below four bits the star moves down a model."""
    result = catalog(BUDGETS["unified-8gb"])
    star = next(r for r in result.rows if r.id == result.recommended_id)

    (picked,) = [b for b in star.builds if b.recommended]
    assert not picked.build.quantization.removeprefix("UD-").startswith(("Q2", "Q3"))
    assert picked.badge.level is BadgeLevel.NONE
