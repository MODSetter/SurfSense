"""Which proxy provider the scrapers use: the vendor SCRAPING_PROXY_PROVIDER names, or none."""

import pytest

from proprietary.scraping.config import Config
from proprietary.scraping.proxy import get_proxy_url, get_sticky_proxy_url, registry
from proprietary.scraping.proxy.providers.dataimpulse import DataImpulseProvider
from proprietary.scraping.proxy.providers.nodemaven import NodeMavenProvider


@pytest.fixture(autouse=True)
def _reset_active_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear the process-wide provider cache so each test resolves fresh."""
    monkeypatch.setattr(registry, "_active_provider", None)


@pytest.mark.parametrize("unset", [None, "", "  "])
def test_no_provider_scrapes_direct(
    monkeypatch: pytest.MonkeyPatch, unset: str | None
) -> None:
    """Development and tests: no vendor, so no proxy, sticky or not."""
    monkeypatch.setattr(Config, "PROXY_PROVIDER", unset)

    assert get_proxy_url() is None
    assert get_sticky_proxy_url("s1", "us") is None


def test_resolves_dataimpulse(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "PROXY_PROVIDER", "dataimpulse")
    assert isinstance(registry.get_active_provider(), DataImpulseProvider)


def test_resolves_nodemaven(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "PROXY_PROVIDER", " nodemaven ")
    assert isinstance(registry.get_active_provider(), NodeMavenProvider)


def test_an_unknown_provider_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A typo must not quietly scrape from the container's own address."""
    monkeypatch.setattr(Config, "PROXY_PROVIDER", "custom")

    with pytest.raises(ValueError, match="custom"):
        registry.get_active_provider()
