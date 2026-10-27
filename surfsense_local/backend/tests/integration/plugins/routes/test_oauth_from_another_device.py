"""In the Docker image, a plugin sign-in from another device than the host lands on
that device's own origin (docs/proposals/docker/README.md, Sign-ins)."""

from collections.abc import Iterator
from urllib.parse import parse_qs, urlsplit

import pytest
from httpx import AsyncClient

from api.config import get_settings
from tests.integration.plugins.routes.test_oauth_sign_in import (
    SignInServers,
    approve_in_browser,
)
from tests.mcp_test_server import notes_server, serving
from tests.oauth_stand_in import ProtectedByStandIn, StandInAuthorizationServer

pytestmark = pytest.mark.integration

LAN = {"host": "surfsense.lan:4943", "x-forwarded-proto": "https"}
LAN_CALLBACK = "https://surfsense.lan:4943/plugins/oauth/callback"


@pytest.fixture
def servers() -> Iterator[SignInServers]:
    """A provider with dynamic registration, protecting the notes server."""
    authorization = StandInAuthorizationServer()
    with serving(authorization.app()) as issuer:
        authorization.issuer = issuer
        protected = ProtectedByStandIn(
            notes_server().streamable_http_app(), authorization
        )
        with serving(protected) as base:
            yield SignInServers(authorization, protected, f"{base}/mcp")


@pytest.fixture
def in_a_container(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Docker image, published on 4929, with no public domain."""
    monkeypatch.setattr(get_settings(), "runtime", "docker")
    monkeypatch.setattr(get_settings(), "public_port", 4929)
    monkeypatch.setattr(get_settings(), "domain", None)


async def test_a_lan_device_registers_its_own_callback_and_signs_in_there(
    client: AsyncClient, servers: SignInServers, in_a_container: None
) -> None:
    """A LAN name no provider can fetch a document from: it registers dynamically,
    and the provider sends the browser back to the address it is already on."""
    added = await client.post(
        "/plugins/custom", json={"url": servers.mcp_url, "name": "Notes"}, headers=LAN
    )
    assert added.status_code == 201, added.text
    started = await client.post("/plugins/notes/sign-in", headers=LAN)
    assert started.status_code == 202, started.text

    url = started.json()["authorization_url"]
    assert parse_qs(urlsplit(url).query)["redirect_uri"] == [LAN_CALLBACK]
    assert servers.authorization.registered[-1]["redirect_uris"] == [LAN_CALLBACK]
    page = await approve_in_browser(client, url)
    assert "Signed in to Notes" in page.text, page.text


async def test_the_callback_to_register_an_app_with_is_the_devices_own(
    client: AsyncClient, in_a_container: None
) -> None:
    """The user's own app is registered with the callback their browser can reach."""
    answered = await client.get("/plugins/oauth/redirect-uri", headers=LAN)

    assert answered.json() == {"redirect_uri": LAN_CALLBACK}


async def test_the_public_domain_serves_its_own_client_document(
    client: AsyncClient, in_a_container: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A provider fetches it there; any other origin has none."""
    monkeypatch.setattr(get_settings(), "domain", "surfsense.example.com")
    public = {"host": "surfsense.example.com", "x-forwarded-proto": "https"}

    document = await client.get("/plugins/oauth/client.json", headers=public)
    elsewhere = await client.get("/plugins/oauth/client.json", headers=LAN)

    assert document.status_code == 200
    assert document.json()["client_id"] == (
        "https://surfsense.example.com/plugins/oauth/client.json"
    )
    assert document.json()["redirect_uris"] == [
        "https://surfsense.example.com/plugins/oauth/callback"
    ]
    assert elsewhere.status_code == 404
