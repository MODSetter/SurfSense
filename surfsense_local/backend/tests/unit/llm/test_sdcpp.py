from pathlib import Path

import pytest
from fastapi import HTTPException

from modules.llm.catalog.local.dependencies import get_local_catalog
from modules.llm.model_type import ModelType
from modules.llm.providers.sdcpp import provider as sdcpp
from modules.llm.selection import _validate_local_image
from shared.config import get_llm_settings

pytestmark = pytest.mark.unit

SD15 = "v1-5-pruned_Q4_0"


@pytest.fixture
def staged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A build that ships sd-server, its images folder empty."""
    monkeypatch.setattr(get_llm_settings(), "image_models_dir", tmp_path)
    get_local_catalog.cache_clear()
    yield tmp_path
    get_local_catalog.cache_clear()


def test_a_host_without_sd_server_offers_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No models dir means Electron staged no binary: stay silent, do not fail."""
    monkeypatch.setattr(get_llm_settings(), "image_models_dir", None)
    assert sdcpp.offered() is False


def test_the_local_image_model_only_takes_the_image_gen_slot(staged: Path) -> None:
    """It cannot chat, cannot carry a connection, and must be installed first."""
    with pytest.raises(HTTPException, match="does not serve text_gen"):
        _validate_local_image(ModelType.TEXT_GEN, SD15, None)
    with pytest.raises(HTTPException, match="must not include a connection"):
        _validate_local_image(ModelType.IMAGE_GEN, SD15, 1)
    with pytest.raises(HTTPException, match="is not installed"):
        _validate_local_image(ModelType.IMAGE_GEN, SD15, None)

    (staged / f"{SD15}.gguf").write_bytes(b"GGUF")

    _validate_local_image(ModelType.IMAGE_GEN, SD15, None)


def test_base_url_reaches_sd_server_on_the_openai_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The image provider appends /images/generations, so /v1 must be here."""
    monkeypatch.setattr(get_llm_settings(), "image_base_url", "http://127.0.0.1:9/")
    assert sdcpp.base_url() == "http://127.0.0.1:9/v1"
