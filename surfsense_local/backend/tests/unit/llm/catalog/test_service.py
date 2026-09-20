"""The screen's data, assembled without a network call."""

from pathlib import Path

import pytest

from modules.llm.catalog import CatalogService, load_curated_models

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
