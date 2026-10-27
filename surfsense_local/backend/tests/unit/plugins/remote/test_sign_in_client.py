import pytest

from api.config import get_settings
from modules.plugins.lists.registry import registry_origin
from modules.plugins.remote.sign_in.oauth.browser_origin import BrowserOrigin
from modules.plugins.remote.sign_in.oauth.sign_in_client import (
    SignInClient,
    client_document,
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

    assert sign_in_client(BrowserOrigin.loopback(4321)) == SignInClient(
        "https://plugins.surfsense.com/oauth/callback",
        "https://plugins.surfsense.com/oauth/client.json",
    )


def test_an_unpackaged_app_registers_with_its_loopback_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No plugin host serves its document or callback page in development (RFC 8252)."""
    monkeypatch.setattr(registry_origin, "reads_repository", lambda: True)
    monkeypatch.setattr(get_plugin_host_settings(), "plugin_host_url", None)

    assert sign_in_client(BrowserOrigin.loopback(4321)) == LOOPBACK


def test_a_local_plugin_host_registers_with_the_loopback_callback_even_packaged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Its plugin host serves no client document or callback page."""
    monkeypatch.setattr(registry_origin, "reads_repository", lambda: False)
    monkeypatch.setattr(
        get_plugin_host_settings(), "plugin_host_url", "http://127.0.0.1:8000"
    )

    assert sign_in_client(BrowserOrigin.loopback(4321)) == LOOPBACK


def test_a_lan_origin_registers_dynamically_with_its_own_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The callback lands where the browser already is; a LAN name no provider can
    fetch a document from, so it registers instead (docs/proposals/docker)."""
    monkeypatch.setattr(registry_origin, "reads_repository", lambda: False)
    monkeypatch.setattr(get_settings(), "domain", None)

    client = sign_in_client(BrowserOrigin("https", "surfsense.lan", 4943))

    assert client == SignInClient(
        "https://surfsense.lan:4943/plugins/oauth/callback", None
    )


def test_the_public_domain_signs_in_as_its_own_client_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A domain the provider can fetch from, over HTTPS, names its own document."""
    monkeypatch.setattr(registry_origin, "reads_repository", lambda: False)
    monkeypatch.setattr(get_settings(), "domain", "surfsense.example.com")

    client = sign_in_client(BrowserOrigin("https", "surfsense.example.com", 443))

    assert client == SignInClient(
        "https://surfsense.example.com/plugins/oauth/callback",
        "https://surfsense.example.com/plugins/oauth/client.json",
    )


def test_the_document_names_itself_and_only_its_own_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Its client ID is its own address, and its one redirect is the domain's callback."""
    monkeypatch.setattr(get_settings(), "domain", "surfsense.example.com")

    document = client_document(BrowserOrigin("https", "surfsense.example.com", 443))

    assert document is not None
    assert (
        document["client_id"]
        == "https://surfsense.example.com/plugins/oauth/client.json"
    )
    assert document["redirect_uris"] == [
        "https://surfsense.example.com/plugins/oauth/callback"
    ]
    assert document["token_endpoint_auth_method"] == "none"


def test_no_document_is_served_for_an_origin_that_is_not_the_public_domain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A LAN name or the host itself has no document a provider could fetch."""
    monkeypatch.setattr(get_settings(), "domain", "surfsense.example.com")

    assert client_document(BrowserOrigin("https", "surfsense.lan", 4943)) is None
    assert client_document(BrowserOrigin.loopback(4929)) is None
