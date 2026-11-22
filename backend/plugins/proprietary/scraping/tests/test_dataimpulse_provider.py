"""Unit tests for the DataImpulseProvider.

Takes a single full URL; the vendor-specific bit is parsing the
``__cr.<country>`` username suffix for :meth:`get_location`. Playwright/requests
shapes come from the shared base parse, so a couple of checks cover the wiring.
"""

from urllib.parse import urlsplit

import pytest

from proprietary.scraping.config import Config
from proprietary.scraping.proxy.providers.dataimpulse import DataImpulseProvider

_URL = "http://tok123__cr.us:secret@gw.dataimpulse.com:823"


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "PROXY_URL", None)


def test_returns_configured_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "PROXY_URL", _URL)
    provider = DataImpulseProvider()

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


def test_geo_proxy_url_rewrites_country_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "PROXY_URL", _URL)

    result = DataImpulseProvider().get_geo_proxy_url("gb")

    assert result == "http://tok123__cr.gb:secret@gw.dataimpulse.com:823"


def test_geo_proxy_url_replaces_existing_country_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        Config,
        "PROXY_URL",
        "http://tok123__cr.us__sid.old:secret@gw.dataimpulse.com:823",
    )

    result = DataImpulseProvider().get_geo_proxy_url("de")

    assert "__cr.us" not in result
    assert result.count("__cr.de") == 1
    assert "__sid.old" not in result


def test_geo_proxy_url_without_country_keeps_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Config, "PROXY_URL", _URL)

    assert DataImpulseProvider().get_geo_proxy_url(None) == _URL
    assert DataImpulseProvider().get_geo_proxy_url("") == _URL


def test_a_sticky_session_is_a_port_holding_one_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DataImpulse ignores a session id in the user and rotates per request; each
    port from 10000 to 20000 holds one IP (measured live, 2026-10-12)."""
    monkeypatch.setattr(Config, "PROXY_URL", _URL)

    result = DataImpulseProvider().get_sticky_proxy_url("location-123", "gb")

    parts = urlsplit(result)
    assert parts.username == "tok123__cr.gb"
    assert parts.password == "secret"  # pragma: allowlist secret
    assert 10000 <= parts.port <= 20000


def test_one_session_keeps_its_port_and_another_gets_its_own(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Config, "PROXY_URL", _URL)
    provider = DataImpulseProvider()

    first = urlsplit(provider.get_sticky_proxy_url("session-a")).port
    again = urlsplit(provider.get_sticky_proxy_url("session-a")).port
    other = urlsplit(provider.get_sticky_proxy_url("session-b")).port

    assert first == again
    assert first != other


def test_a_country_alone_stays_on_the_rotating_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Config, "PROXY_URL", _URL)

    assert urlsplit(DataImpulseProvider().get_geo_proxy_url("de")).port == 823


def test_no_country_suffix_yields_empty_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Config, "PROXY_URL", "http://tok:secret@gw.dataimpulse.com:823")
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


def test_sticky_slot_is_the_sticky_port(monkeypatch: pytest.MonkeyPatch) -> None:
    """Leases keep live ports distinct, so the slot must be the port itself."""
    monkeypatch.setattr(Config, "PROXY_URL", _URL)
    provider = DataImpulseProvider()

    url = provider.get_sticky_proxy_url("abc123", "gb")

    assert provider.sticky_slot("abc123") == urlsplit(url).port
