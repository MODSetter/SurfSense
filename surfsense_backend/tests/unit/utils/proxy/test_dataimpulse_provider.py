"""Unit tests for the DataImpulseProvider.

Takes a single full URL (like ``custom``); the vendor-specific bit is parsing the
``__cr.<country>`` username suffix for :meth:`get_location`. Playwright/requests
shapes come from the shared base parse, so a couple of checks cover the wiring.
"""

import pytest

from app.config import Config
from app.utils.proxy.providers.dataimpulse import DataImpulseProvider

pytestmark = pytest.mark.unit

_URL = "http://tok123__cr.us:secret@gw.dataimpulse.com:823"


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "PROXY_URL", None)


def test_returns_configured_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "PROXY_URL", _URL)
    provider = DataImpulseProvider()

    assert provider.is_pool_backed is False
    assert provider.get_proxy_url() == _URL
    assert provider.get_requests_proxies() == {"http": _URL, "https": _URL}


def test_location_parsed_from_country_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "PROXY_URL", _URL)
    assert DataImpulseProvider().get_location() == "us"


def test_location_stops_at_next_param(monkeypatch: pytest.MonkeyPatch) -> None:
    # A sticky/session suffix after the country must not bleed into the location.
    monkeypatch.setattr(
        Config,
        "PROXY_URL",
        "http://tok__cr.de__sid.abc123:secret@gw.dataimpulse.com:823",
    )
    assert DataImpulseProvider().get_location() == "de"


def test_no_country_suffix_yields_empty_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        Config, "PROXY_URL", "http://tok:secret@gw.dataimpulse.com:823"
    )
    assert DataImpulseProvider().get_location() == ""


def test_unconfigured_returns_none() -> None:
    provider = DataImpulseProvider()

    assert provider.get_proxy_url() is None
    assert provider.get_requests_proxies() is None
    assert provider.get_playwright_proxy() is None
    assert provider.get_location() == ""


def test_playwright_proxy_from_base_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "PROXY_URL", _URL)

    assert DataImpulseProvider().get_playwright_proxy() == {
        "server": "http://gw.dataimpulse.com:823",
        "username": "tok123__cr.us",
        "password": "secret",
    }
