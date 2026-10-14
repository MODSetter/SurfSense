import pytest

from modules.plugins.lists.registry import registry_origin
from modules.plugins.remote.sign_in.oauth.sign_in_client import (
    SignInClient,
    sign_in_client,
)
from shared.config import get_plugin_host_settings

pytestmark = pytest.mark.unit

LOOPBACK = SignInClient("http://127.0.0.1:4321/plugins/oauth/callback", None)


def test_a_packaged_app_signs_in_as_surfsenses_app_on_the_plugin_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Its client ID metadata document names the plugin host's callback page."""
    monkeypatch.setattr(registry_origin, "reads_repository", lambda: False)
    monkeypatch.setattr(get_plugin_host_settings(), "plugin_host_url", None)

    assert sign_in_client(4321) == SignInClient(
        "https://plugins.surfsense.com/oauth/callback",
        "https://plugins.surfsense.com/oauth/client.json",
    )


def test_an_unpackaged_app_registers_with_its_loopback_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No plugin host serves its document or callback page in development (RFC 8252)."""
    monkeypatch.setattr(registry_origin, "reads_repository", lambda: True)
    monkeypatch.setattr(get_plugin_host_settings(), "plugin_host_url", None)

    assert sign_in_client(4321) == LOOPBACK


def test_a_local_plugin_host_registers_with_the_loopback_callback_even_packaged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Its plugin host serves no client document or callback page."""
    monkeypatch.setattr(registry_origin, "reads_repository", lambda: False)
    monkeypatch.setattr(
        get_plugin_host_settings(), "plugin_host_url", "http://127.0.0.1:8000"
    )

    assert sign_in_client(4321) == LOOPBACK
