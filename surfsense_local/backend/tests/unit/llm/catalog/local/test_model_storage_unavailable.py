"""A download waits for the drive the user chose, rather than landing on another."""

import pytest

from modules.llm.catalog.local.install.codes import InstallCode
from modules.llm.catalog.local.install.plan import InstallRefusedError
from modules.llm.catalog.local.install.storage_available import (
    refuse_while_storage_is_missing,
)
from shared.config import get_storage_settings


@pytest.fixture(autouse=True)
def _fresh_settings():
    get_storage_settings.cache_clear()
    yield
    get_storage_settings.cache_clear()


def test_a_download_is_refused_while_the_models_drive_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The interface has its own words for this code, in each language."""
    monkeypatch.setenv("SURFSENSE_LOCAL_MODEL_STORAGE_UNAVAILABLE", "1")

    with pytest.raises(InstallRefusedError) as refused:
        refuse_while_storage_is_missing()

    assert refused.value.code is InstallCode.MODEL_STORAGE_UNAVAILABLE


def test_a_download_goes_ahead_when_the_folder_is_there(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unset, as on every install that never moved its models."""
    monkeypatch.delenv("SURFSENSE_LOCAL_MODEL_STORAGE_UNAVAILABLE", raising=False)

    refuse_while_storage_is_missing()
