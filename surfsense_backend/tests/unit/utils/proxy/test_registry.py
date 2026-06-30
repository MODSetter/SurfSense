"""Unit tests for proxy provider selection (Phase 3b).

``PROXY_PROVIDER`` selects the single app-wide provider; ``custom`` is now
registered alongside ``anonymous_proxies``, and unknown values still warn and
fall back to the default.
"""

import pytest

from app.config import Config
from app.utils.proxy import registry
from app.utils.proxy.providers.anonymous_proxies import AnonymousProxiesProvider
from app.utils.proxy.providers.custom import CustomProxyProvider

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_active_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear the process-wide provider cache so each test resolves fresh."""
    monkeypatch.setattr(registry, "_active_provider", None)


def test_resolves_custom(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "PROXY_PROVIDER", "custom")
    assert isinstance(registry.get_active_provider(), CustomProxyProvider)


def test_resolves_anonymous(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "PROXY_PROVIDER", "anonymous_proxies")
    assert isinstance(registry.get_active_provider(), AnonymousProxiesProvider)


def test_unknown_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "PROXY_PROVIDER", "does_not_exist")
    assert isinstance(registry.get_active_provider(), AnonymousProxiesProvider)
