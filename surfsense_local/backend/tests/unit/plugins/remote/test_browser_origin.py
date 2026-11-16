from types import SimpleNamespace

import pytest

from api.config import get_settings
from modules.plugins.remote.sign_in.oauth.browser_origin import (
    BrowserOrigin,
    browser_origin,
)

pytestmark = pytest.mark.unit


def _request(host: str, proto: str = "https") -> object:
    """A request as Caddy forwards it: the browser's Host and scheme."""
    return SimpleNamespace(headers={"host": host, "x-forwarded-proto": proto})


def test_in_the_container_a_sign_in_returns_to_the_address_the_browser_is_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Caddy and the access service have vetted the Host by now."""
    monkeypatch.setattr(get_settings(), "runtime", "docker")

    assert browser_origin(_request("surfsense.lan:4943")) == BrowserOrigin(
        "https", "surfsense.lan", 4943
    )
    assert browser_origin(_request("surfsense.example.com")) == BrowserOrigin(
        "https", "surfsense.example.com", 443
    )


def test_the_host_itself_is_the_loopback_origin_on_the_published_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On the host, the plugin host's page forwards to the port the browser came in on."""
    monkeypatch.setattr(get_settings(), "runtime", "docker")
    monkeypatch.setattr(get_settings(), "public_port", 4929)

    origin = browser_origin(_request("localhost:4929", "http"))

    assert origin == BrowserOrigin.loopback(4929)
    assert origin.is_loopback


def test_on_the_desktop_a_host_header_is_never_trusted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A page rebinding a name to the loopback API chooses its own Host."""
    monkeypatch.setattr(get_settings(), "runtime", None)
    monkeypatch.setattr(get_settings(), "public_port", None)
    monkeypatch.setattr(get_settings(), "port", 8123)

    assert browser_origin(_request("attacker.example")) == BrowserOrigin.loopback(8123)
