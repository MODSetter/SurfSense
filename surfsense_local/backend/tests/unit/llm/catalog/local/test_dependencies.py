"""A broken packaged manifest still starts the catalog, and says why."""

import logging

import pytest

import modules.llm.catalog.local.dependencies as dependencies
from modules.llm.catalog.local.dependencies import get_local_catalog

pytestmark = pytest.mark.unit


@pytest.fixture
def cold_catalog():
    """A fresh catalog per test: get_local_catalog is process cached."""
    get_local_catalog.cache_clear()
    yield
    get_local_catalog.cache_clear()


def test_a_broken_manifest_logs_why_and_still_starts(
    cold_catalog, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The curated rows go missing, but the reason stays in the log."""

    def broken() -> object:
        raise ValueError("unexpected schema version 99")

    monkeypatch.setattr(dependencies, "load_local_manifest", broken)
    with caplog.at_level(
        logging.WARNING, logger="modules.llm.catalog.local.dependencies"
    ):
        service = get_local_catalog()

    assert service._manifest.models == []
    assert "local model manifest unavailable" in caplog.text
    assert "unexpected schema version 99" in caplog.text
