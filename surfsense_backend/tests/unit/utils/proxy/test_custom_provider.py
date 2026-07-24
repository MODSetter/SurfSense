"""Unit tests for the BYO ``CustomProxyProvider`` (Phase 3b).

Covers single-endpoint vs pool behavior, cyclic rotation, env de-duplication,
the empty/unconfigured case, and the playwright-dict parse.
"""

import pytest

from app.config import Config
from app.utils.proxy.providers.custom import CustomProxyProvider

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clear_proxy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default both knobs to unset; individual tests set what they need."""
    monkeypatch.setattr(Config, "PROXY_URL", None)
    monkeypatch.setattr(Config, "PROXY_URLS", None)


def test_single_url_is_static(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "PROXY_URL", "http://u:p@host:8080")
    provider = CustomProxyProvider()

    assert provider.is_pool_backed is False
    assert provider.get_proxy_url() == "http://u:p@host:8080"
    # Static endpoint returns the same value every call.
    assert provider.get_proxy_url() == "http://u:p@host:8080"


def test_pool_rotates_cyclically(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        Config,
        "PROXY_URLS",
        "http://a:1@h1:8080, http://b:2@h2:8080 ,http://c:3@h3:8080",
    )
    provider = CustomProxyProvider()

    assert provider.is_pool_backed is True
    seen = [provider.get_proxy_url() for _ in range(4)]
    assert seen == [
        "http://a:1@h1:8080",
        "http://b:2@h2:8080",
        "http://c:3@h3:8080",
        "http://a:1@h1:8080",  # wraps around
    ]


def test_single_plus_pool_dedupes(monkeypatch: pytest.MonkeyPatch) -> None:
    """A URL present in both PROXY_URL and the pool is not duplicated."""
    monkeypatch.setattr(Config, "PROXY_URLS", "http://a@h1:80,http://b@h2:80")
    monkeypatch.setattr(Config, "PROXY_URL", "http://a@h1:80")
    provider = CustomProxyProvider()

    assert provider.is_pool_backed is True
    seen = [provider.get_proxy_url() for _ in range(3)]
    assert seen == ["http://a@h1:80", "http://b@h2:80", "http://a@h1:80"]


def test_unconfigured_returns_none() -> None:
    provider = CustomProxyProvider()

    assert provider.is_pool_backed is False
    assert provider.get_proxy_url() is None
    assert provider.get_requests_proxies() is None


def test_playwright_proxy_parses_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Config, "PROXY_URL", "http://user:pass@host:8080")
    provider = CustomProxyProvider()

    assert provider.get_playwright_proxy() == {
        "server": "http://host:8080",
        "username": "user",
        "password": "pass",
    }
