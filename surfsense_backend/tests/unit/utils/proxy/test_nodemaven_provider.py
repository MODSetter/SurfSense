"""Unit tests for the NodeMavenProvider.

Takes a single full URL (like ``custom``); the vendor-specific bit is the
``-country-<cc>`` / ``-sid-<id>`` username syntax used for geoip-match, country
routing and sticky sessions.
"""

import pytest

from app.config import Config
from app.utils.proxy.providers.nodemaven import NodeMavenProvider

pytestmark = pytest.mark.unit

_URL = "http://acct-country-us:secret@gate.nodemaven.com:8080"


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "PROXY_URL", None)


def test_returns_configured_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "PROXY_URL", _URL)
    provider = NodeMavenProvider()

    assert provider.is_pool_backed is False
    assert provider.get_proxy_url() == _URL
    assert provider.get_requests_proxies() == {"http": _URL, "https": _URL}


def test_location_parsed_from_country_param(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "PROXY_URL", _URL)
    assert NodeMavenProvider().get_location() == "us"


def test_location_stops_at_next_param(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        Config,
        "PROXY_URL",
        "http://acct-country-de-city-berlin-sid-abc123:secret@gate.nodemaven.com:8080",
    )
    assert NodeMavenProvider().get_location() == "de"


def test_geo_proxy_url_replaces_country_and_drops_its_locations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        Config,
        "PROXY_URL",
        "http://acct-country-us-region-texas-city-austin-sid-old-ttl-10m:secret@gate.nodemaven.com:8080",
    )

    result = NodeMavenProvider().get_geo_proxy_url("gb")

    assert result == "http://acct-ttl-10m-country-gb:secret@gate.nodemaven.com:8080"


def test_geo_proxy_url_same_country_keeps_region(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        Config,
        "PROXY_URL",
        "http://acct-country-us-region-texas:secret@gate.nodemaven.com:8080",
    )

    result = NodeMavenProvider().get_geo_proxy_url("US")

    assert (
        result == "http://acct-country-us-region-texas:secret@gate.nodemaven.com:8080"
    )


def test_geo_proxy_url_without_country_keeps_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Config, "PROXY_URL", _URL)

    assert NodeMavenProvider().get_geo_proxy_url(None) == _URL
    assert NodeMavenProvider().get_geo_proxy_url("") == _URL


def test_sticky_proxy_url_composes_country_and_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Config, "PROXY_URL", _URL)

    result = NodeMavenProvider().get_sticky_proxy_url("location-123", "gb")

    assert result == (
        "http://acct-country-gb-sid-location123:secret@gate.nodemaven.com:8080"
    )


def test_sticky_proxy_url_replaces_existing_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        Config,
        "PROXY_URL",
        "http://acct-country-us-sid-old:secret@gate.nodemaven.com:8080",
    )

    result = NodeMavenProvider().get_sticky_proxy_url("new1")

    assert result == "http://acct-country-us-sid-new1:secret@gate.nodemaven.com:8080"


def test_sticky_proxy_url_rejects_empty_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Config, "PROXY_URL", _URL)

    with pytest.raises(ValueError):
        NodeMavenProvider().get_sticky_proxy_url("---")


def test_password_with_reserved_characters_round_trips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        Config,
        "PROXY_URL",
        "http://acct-country-us:p%40ss%2Fw@gate.nodemaven.com:8080",
    )

    result = NodeMavenProvider().get_sticky_proxy_url("s1")

    assert result == "http://acct-country-us-sid-s1:p%40ss%2Fw@gate.nodemaven.com:8080"


def test_no_country_param_yields_empty_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        Config, "PROXY_URL", "http://acct:secret@gate.nodemaven.com:8080"
    )
    assert NodeMavenProvider().get_location() == ""


def test_unconfigured_returns_none() -> None:
    provider = NodeMavenProvider()

    assert provider.get_proxy_url() is None
    assert provider.get_requests_proxies() is None
    assert provider.get_playwright_proxy() is None
    assert provider.get_location() == ""
    assert provider.get_sticky_proxy_url("s1") is None


def test_playwright_proxy_from_base_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "PROXY_URL", _URL)

    assert NodeMavenProvider().get_playwright_proxy() == {
        "server": "http://gate.nodemaven.com:8080",
        "username": "acct-country-us",
        "password": "secret",
    }
