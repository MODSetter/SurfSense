from dataclasses import replace
from pathlib import Path

import pytest
from fastapi import HTTPException

from modules.llm.models import ModelRole
from modules.llm.providers.sdcpp import provider as sdcpp
from modules.llm.selection import _validate_local_image
from shared.config import get_llm_settings

pytestmark = pytest.mark.unit

# Small enough to write, so the size gate can be exercised without 2.8 GB.
SMALL = 2048


@pytest.fixture
def staged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A staged sd-server whose catalogue expects files a test can write."""
    monkeypatch.setattr(get_llm_settings(), "image_models_dir", tmp_path)
    monkeypatch.setattr(
        sdcpp,
        "CATALOG",
        tuple(replace(model, size_bytes=SMALL) for model in sdcpp.CATALOG),
    )
    return tmp_path


def _download(directory: Path, model: sdcpp.ImageModel) -> None:
    (directory / model.file).write_bytes(b"\0" * model.size_bytes)


def test_a_host_without_sd_server_offers_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No models dir means Electron staged no binary: stay silent, do not fail."""
    monkeypatch.setattr(get_llm_settings(), "image_models_dir", None)
    assert sdcpp.offered() is False
    assert all(sdcpp.installed(model) is False for model in sdcpp.CATALOG)


def test_every_catalogue_entry_is_a_distinct_single_file(staged: Path) -> None:
    """Electron launches on the filename, so two models cannot share one."""
    files = [model.file for model in sdcpp.CATALOG]
    names = [model.name for model in sdcpp.CATALOG]
    assert len(set(files)) == len(files)
    assert len(set(names)) == len(names)
    assert all(sdcpp.find(name) is not None for name in names)
    assert sdcpp.find("not-a-model") is None


def test_installed_does_not_depend_on_the_catalogue_byte_count(
    staged: Path,
) -> None:
    """A stale size_bytes must not read as "never downloaded".

    install() renames only after the SHA matches, so the name is the guarantee.
    Requiring an exact size instead left two models stuck on Download forever,
    because the catalogue carried a rounded count.
    """
    model = sdcpp.CATALOG[0]
    assert sdcpp.offered() is True
    assert sdcpp.installed(model) is False

    (staged / model.file).write_bytes(b"\0" * (model.size_bytes + 977))
    assert sdcpp.installed(model) is True

    # Downloading one model says nothing about the others.
    assert sdcpp.installed(sdcpp.CATALOG[1]) is False


def test_an_empty_file_is_not_a_model(staged: Path) -> None:
    """Nothing writes a zero-byte file here, so treat one as absent."""
    model = sdcpp.CATALOG[0]
    (staged / model.file).write_bytes(b"")
    assert sdcpp.installed(model) is False


def test_the_local_image_model_only_takes_the_image_role(staged: Path) -> None:
    """It cannot chat, cannot carry a connection, and must be downloaded first."""
    model = sdcpp.CATALOG[0]
    _download(staged, model)

    with pytest.raises(HTTPException, match="does not answer chat"):
        _validate_local_image(ModelRole.GENERATION, model.name, None)
    with pytest.raises(HTTPException, match="must not include a connection"):
        _validate_local_image(ModelRole.IMAGE_GENERATION, model.name, 1)
    with pytest.raises(HTTPException, match="unknown local image model"):
        _validate_local_image(ModelRole.IMAGE_GENERATION, "sd-cpp-local", None)

    _validate_local_image(ModelRole.IMAGE_GENERATION, model.name, None)

    # A catalogued model that was never downloaded is refused by name.
    with pytest.raises(HTTPException, match="is not installed"):
        _validate_local_image(
            ModelRole.IMAGE_GENERATION, sdcpp.CATALOG[1].name, None
        )


def test_base_url_reaches_sd_server_on_the_openai_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The image provider appends /images/generations, so /v1 must be here."""
    monkeypatch.setattr(get_llm_settings(), "image_base_url", "http://127.0.0.1:9/")
    assert sdcpp.base_url() == "http://127.0.0.1:9/v1"
