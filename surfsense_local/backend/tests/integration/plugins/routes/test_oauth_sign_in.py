"""Signing in to a plugin with OAuth, through the connect routes, against a stand-in authorization server."""

import asyncio
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from httpx import AsyncClient

from modules.plugins.lists.registry import registry_keys, registry_origin
from modules.plugins.remote.sign_in.oauth import plugin_sign_ins
from shared.config import get_plugin_host_settings
from tests.mcp_test_server import notes_server, serving
from tests.oauth_stand_in import ProtectedByStandIn, StandInAuthorizationServer
from tests.registry_stand_in import StandInRegistry, entry

pytestmark = pytest.mark.integration


@dataclass
class SignInServers:
    authorization: StandInAuthorizationServer
    protected: ProtectedByStandIn
    mcp_url: str


@pytest.fixture
def servers() -> Iterator[SignInServers]:
    """An authorization server and the notes server it protects, each on its own loopback port."""
    authorization = StandInAuthorizationServer()
    with serving(authorization.app()) as issuer:
        authorization.issuer = issuer
        notes = notes_server()
        protected = ProtectedByStandIn(notes.streamable_http_app(), authorization)
        with serving(protected) as base:
            yield SignInServers(authorization, protected, f"{base}/mcp")


@dataclass
class RegistryServers:
    registry: StandInRegistry
    authorization: StandInAuthorizationServer
    protected: ProtectedByStandIn


@pytest.fixture
def registry(monkeypatch: pytest.MonkeyPatch) -> Iterator[RegistryServers]:
    """The stand-in plugin host serving the registry and the notes server, which the
    authorization server protects."""
    authorization = StandInAuthorizationServer()
    stand_in = StandInRegistry()
    notes = notes_server()
    protected = ProtectedByStandIn(notes.streamable_http_app(), authorization)
    app = stand_in.app({"notes": protected}, [notes])
    monkeypatch.setattr(registry_origin, "reads_repository", lambda: False)
    monkeypatch.setattr(
        registry_keys, "REGISTRY_PUBLIC_KEYS_HEX", (stand_in.public_key_hex,)
    )
    with serving(authorization.app()) as issuer, serving(app) as base:
        authorization.issuer = issuer
        monkeypatch.setattr(get_plugin_host_settings(), "plugin_host_url", base)
        yield RegistryServers(stand_in, authorization, protected)


async def allow_third_party(client: AsyncClient) -> None:
    """Turn third-party plugins on, as the switch's Allow does."""
    allowed = await client.put("/plugins/third-party", json={"allowed": True})
    assert allowed.status_code == 204


async def approve_in_browser(
    client: AsyncClient, authorization_url: str
) -> httpx.Response:
    """What the user's browser does: open the page, click Allow, land on the API's callback."""
    async with httpx.AsyncClient() as browser:
        approved = await browser.get(authorization_url)
    assert approved.status_code == 302, approved.text
    back = urlsplit(approved.headers["location"])
    # The plugin host's callback page forwards the same query to the API's own port.
    path = (
        "/plugins/oauth/callback"
        if back.hostname == "plugins.surfsense.com"
        else back.path
    )
    return await client.get(f"{path}?{back.query}")


async def test_a_custom_server_asking_for_oauth_is_added_to_connect_from_its_row(
    client: AsyncClient, servers: SignInServers
) -> None:
    """Add saves it, signed out: nothing is registered and no sign-in starts until Connect."""
    added = await client.post(
        "/plugins/custom", json={"url": servers.mcp_url, "name": "Notes"}
    )

    assert added.status_code == 201, added.text
    assert added.json()["never_signed_in"] is True
    assert added.json()["check_failure"] == "sign_in"
    assert servers.authorization.registered == []
    await _waiting_to_sign_in(client)


async def test_a_custom_server_asking_for_oauth_signs_in_and_lists_its_tools(
    client: AsyncClient, servers: SignInServers
) -> None:
    """Discovery, registration and PKCE, the code back on the API's port, a stored token."""
    sign_in = await start_custom(client, servers)
    query = parse_qs(urlsplit(sign_in["authorization_url"]).query)
    assert query["redirect_uri"] == ["http://127.0.0.1:8000/plugins/oauth/callback"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["state"][0].startswith("8000.")
    assert servers.authorization.registered[0]["token_endpoint_auth_method"] == "none"

    page = await approve_in_browser(client, sign_in["authorization_url"])

    assert page.status_code == 200
    assert "Signed in to Notes" in page.text
    status = (await client.get(f"/plugins/sign-ins/{sign_in['id']}")).json()
    assert status["status"] == "connected"
    assert status["plugin_id"] == "notes"
    listed = (await client.get("/plugins")).json()
    assert [t["name"] for t in listed[0]["tools"]] == ["search", "count"]
    assert listed[0]["auth_type"] == "oauth"
    assert listed[0]["check_failure"] is None
    assert servers.protected.authorizations[-1] == "Bearer at-1"
    assert "at-1" not in (await client.get("/plugins")).text


async def test_a_registry_plugin_signing_in_with_oauth_connects_once_signed_in(
    client: AsyncClient, registry: RegistryServers
) -> None:
    """Connect answers with the page to open; the plugin waits, signed out, until the callback."""
    registry.registry.publish([entry("notes", auth={"type": "oauth"})])
    await allow_third_party(client)

    started = await client.post("/plugins/registry/notes")
    assert started.status_code == 202, started.text
    await _waiting_to_sign_in(client)

    page = await approve_in_browser(client, started.json()["authorization_url"])

    assert "Signed in to Notes" in page.text
    listed = (await client.get("/plugins")).json()
    assert [(p["id"], p["source"], p["auth_type"]) for p in listed] == [
        ("notes", "registry", "oauth")
    ]
    assert registry.protected.authorizations[-1] == "Bearer at-1"


async def test_a_pre_registered_client_and_its_scopes_are_used_without_registering(
    client: AsyncClient, registry: RegistryServers
) -> None:
    """A provider that registers clients only in advance gets SurfSense's app by its id."""
    registry.registry.publish(
        [
            entry(
                "notes",
                auth={
                    "type": "oauth",
                    "client_id": "app-1",
                    "scopes": ["read", "write"],
                },
            )
        ]
    )
    await allow_third_party(client)

    started = await client.post("/plugins/registry/notes")
    query = parse_qs(urlsplit(started.json()["authorization_url"]).query)
    await approve_in_browser(client, started.json()["authorization_url"])

    assert query["client_id"] == ["app-1"]
    assert query["scope"] == ["read write"]
    assert registry.authorization.registered == []
    assert (await client.get("/plugins")).json()[0]["check_failure"] is None


async def start_custom(client: AsyncClient, servers: SignInServers) -> dict:
    """Add the notes server by URL, then Connect on its row, as the screen does."""
    await allow_third_party(client)
    added = await client.post(
        "/plugins/custom", json={"url": servers.mcp_url, "name": "Notes"}
    )
    assert added.status_code == 201, added.text
    started = await client.post("/plugins/notes/sign-in")
    assert started.status_code == 202, started.text
    return started.json()


@pytest.fixture
def sse_servers() -> Iterator[SignInServers]:
    """The notes server on the older SSE transport only, behind sign-in, as Asana's `/sse`
    is: its POST answers 401 before any transport is chosen."""
    authorization = StandInAuthorizationServer()
    with serving(authorization.app()) as issuer:
        authorization.issuer = issuer
        protected = ProtectedByStandIn(notes_server().sse_app(), authorization)
        with serving(protected) as base:
            yield SignInServers(authorization, protected, f"{base}/sse")


async def test_an_sse_address_asking_for_sign_in_is_refused_before_any_sign_in(
    client: AsyncClient, sse_servers: SignInServers
) -> None:
    """Its POST would ask for sign-in, for an address no engine could call: the user
    is told at once, and never sent to sign in."""
    refused = await client.post(
        "/plugins/custom", json={"url": sse_servers.mcp_url, "name": "Notes"}
    )

    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"]["code"] == "plugin_sse_only"
    assert (await client.get("/plugins")).json() == []


async def test_a_state_the_app_did_not_issue_is_refused_and_changes_nothing(
    client: AsyncClient, servers: SignInServers
) -> None:
    """Another nonce, or one not shaped as SurfSense's, finds no sign-in to finish."""
    sign_in = await start_custom(client, servers)

    forged = await client.get(
        "/plugins/oauth/callback",
        params={"code": "c", "state": "8000.AAAAAAAAAAAAAAAAAAAAAAAA"},
    )
    shapeless = await client.get(
        "/plugins/oauth/callback", params={"code": "c", "state": "anything"}
    )

    assert forged.status_code == shapeless.status_code == 400
    assert "isn't one SurfSense started" in forged.text
    status = (await client.get(f"/plugins/sign-ins/{sign_in['id']}")).json()
    assert status["status"] == "waiting"
    assert servers.authorization.token_requests == []


async def test_a_provider_refusal_ends_the_sign_in_keeping_the_plugin_to_sign_in(
    client: AsyncClient, servers: SignInServers
) -> None:
    """The user clicking Deny comes back as `error=access_denied`."""
    servers.authorization.deny_with = "access_denied"
    sign_in = await start_custom(client, servers)

    page = await approve_in_browser(client, sign_in["authorization_url"])

    assert page.status_code == 400
    assert "Couldn't sign in to Notes" in page.text
    status = (await client.get(f"/plugins/sign-ins/{sign_in['id']}")).json()
    assert (status["status"], status["code"], status["message"]) == (
        "failed",
        "sign_in_declined",
        "The sign-in was declined.",
    )
    assert (status["host"], status["name"]) == (None, None)
    await _waiting_to_sign_in(client)


async def test_any_other_provider_refusal_ends_the_sign_in_as_refused(
    client: AsyncClient, servers: SignInServers
) -> None:
    """An `error` other than `access_denied` is the provider's refusal, named in the sentence."""
    servers.authorization.deny_with = "server_error"
    sign_in = await start_custom(client, servers)

    page = await approve_in_browser(client, sign_in["authorization_url"])

    assert page.status_code == 400
    status = (await client.get(f"/plugins/sign-ins/{sign_in['id']}")).json()
    assert (status["status"], status["code"], status["message"]) == (
        "failed",
        "sign_in_refused",
        "The sign-in was refused (server_error).",
    )
    await _waiting_to_sign_in(client)


async def test_an_abandoned_sign_in_expires_keeping_the_plugin_to_sign_in(
    client: AsyncClient, servers: SignInServers, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Once it expires, the browser's late answer finds nothing to finish."""
    monkeypatch.setattr(plugin_sign_ins, "SIGN_IN_SECONDS", 0.5)
    sign_in = await start_custom(client, servers)
    await asyncio.sleep(0.8)

    status = (await client.get(f"/plugins/sign-ins/{sign_in['id']}")).json()
    late = await approve_in_browser(client, sign_in["authorization_url"])

    assert (status["status"], status["code"], status["message"]) == (
        "failed",
        "sign_in_timed_out",
        "The sign-in was not finished in time.",
    )
    assert late.status_code == 400
    await _waiting_to_sign_in(client)
    assert servers.authorization.token_requests == []


async def test_a_cancelled_sign_in_is_forgotten_keeping_the_plugin_to_sign_in(
    client: AsyncClient, servers: SignInServers
) -> None:
    """Cancel on the screen ends it; finishing it in the browser afterwards does nothing."""
    sign_in = await start_custom(client, servers)

    cancelled = await client.delete(f"/plugins/sign-ins/{sign_in['id']}")
    late = await approve_in_browser(client, sign_in["authorization_url"])

    assert cancelled.status_code == 204
    assert (await client.get(f"/plugins/sign-ins/{sign_in['id']}")).status_code == 404
    assert late.status_code == 400
    await _waiting_to_sign_in(client)
    assert servers.authorization.token_requests == []


async def test_turning_third_party_plugins_off_ends_a_sign_in_under_way(
    client: AsyncClient, servers: SignInServers
) -> None:
    """It would reach the provider once the browser came back; it is forgotten instead."""
    sign_in = await start_custom(client, servers)

    await client.put("/plugins/third-party", json={"allowed": False})
    late = await approve_in_browser(client, sign_in["authorization_url"])

    assert (await client.get(f"/plugins/sign-ins/{sign_in['id']}")).status_code == 404
    assert late.status_code == 400
    assert servers.authorization.token_requests == []


async def test_a_plugin_left_signed_out_signs_in_later_from_its_row(
    client: AsyncClient, servers: SignInServers
) -> None:
    """Nothing is typed again: Sign in on the kept plugin finishes what Add started."""
    first = await start_custom(client, servers)
    await client.delete(f"/plugins/sign-ins/{first['id']}")

    again = await client.post("/plugins/notes/sign-in")
    await approve_in_browser(client, again.json()["authorization_url"])

    listed = (await client.get("/plugins")).json()
    assert len(listed) == 1
    assert listed[0]["check_failure"] is None
    assert listed[0]["never_signed_in"] is False
    assert [t["name"] for t in listed[0]["tools"]] == ["search", "count"]


async def _waiting_to_sign_in(client: AsyncClient) -> None:
    """Kept as the user added it, signed out, with nothing to offer until they sign in."""
    (plugin,) = (await client.get("/plugins")).json()
    assert (plugin["id"], plugin["auth_type"]) == ("notes", "oauth")
    assert plugin["check_failure"] == "sign_in"
    assert plugin["never_signed_in"] is True
    assert plugin["tools"] == []


async def test_the_authorization_servers_host_is_asked_about_before_any_request(
    client: AsyncClient,
) -> None:
    """Discovery names it; the refusal names it for the egress prompt, and nothing is started."""
    authorization = StandInAuthorizationServer()
    notes = notes_server()
    protected = ProtectedByStandIn(
        notes.streamable_http_app(),
        authorization,
        authorization_server="https://auth.example.test",
    )
    with serving(protected) as base:
        started = await client.post(
            "/plugins/custom", json={"url": f"{base}/mcp", "name": "Notes"}
        )

    assert started.status_code == 403
    detail = started.json()["detail"]
    assert detail["code"] == "egress_disabled"
    assert (detail["hosts"], detail["purpose"]) == (["auth.example.test"], "plugin")
    assert (await client.get("/plugins")).json() == []
    network = (await client.get("/egress")).json()
    assert {"host": "auth.example.test", "enabled": False}.items() <= next(
        d for d in network if d["host"] == "auth.example.test"
    ).items()


async def test_a_packaged_app_signs_in_as_surfsenses_app_through_the_plugin_host(
    client: AsyncClient, servers: SignInServers, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With a client ID metadata document supported, nothing is registered, and the
    provider sends the browser to the plugin host's callback page, which forwards it here."""
    monkeypatch.setattr(registry_origin, "reads_repository", lambda: False)
    servers.authorization.supports_client_metadata_document = True

    sign_in = await start_custom(client, servers)
    query = parse_qs(urlsplit(sign_in["authorization_url"]).query)
    page = await approve_in_browser(client, sign_in["authorization_url"])

    assert query["client_id"] == ["https://plugins.surfsense.com/oauth/client.json"]
    assert query["redirect_uri"] == ["https://plugins.surfsense.com/oauth/callback"]
    assert servers.authorization.registered == []
    assert page.status_code == 200


async def test_a_packaged_app_signs_in_where_only_client_documents_are_taken(
    client: AsyncClient, servers: SignInServers, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No registration endpoint is not "needs your own app" while SurfSense's document is taken."""
    monkeypatch.setattr(registry_origin, "reads_repository", lambda: False)
    servers.authorization.supports_client_metadata_document = True
    servers.authorization.registration = False

    sign_in = await start_custom(client, servers)
    query = parse_qs(urlsplit(sign_in["authorization_url"]).query)

    assert query["client_id"] == ["https://plugins.surfsense.com/oauth/client.json"]
    assert servers.authorization.registration_attempts == 0


async def sign_in_custom(client: AsyncClient, servers: SignInServers) -> None:
    """Add the notes server by URL and approve its sign-in in the browser."""
    sign_in = await start_custom(client, servers)
    page = await approve_in_browser(client, sign_in["authorization_url"])
    assert page.status_code == 200, page.text


async def test_a_refused_token_is_refreshed_once_and_the_listing_retried(
    client: AsyncClient, servers: SignInServers
) -> None:
    """The server's 401 on Check now: one refresh, then the listing again with the new token."""
    await sign_in_custom(client, servers)
    servers.authorization.expire_access_tokens()

    checked = await client.post("/plugins/notes/check")

    assert checked.status_code == 200
    assert checked.json()["check_failure"] is None
    grants = [r["grant_type"] for r in servers.authorization.token_requests]
    assert grants == ["authorization_code", "refresh_token"]
    assert servers.protected.authorizations[-1] == "Bearer at-2"


async def test_a_refused_refresh_marks_the_plugin_to_sign_in_again(
    client: AsyncClient, servers: SignInServers
) -> None:
    """A revoked grant: the check says sign in, and the old token is not sent again."""
    await sign_in_custom(client, servers)
    servers.authorization.expire_access_tokens()
    servers.authorization.refuse_refresh = True

    checked = await client.post("/plugins/notes/check")

    assert checked.json()["check_failure"] == "sign_in"
    # Signed in once: it signs in again, not connects for the first time.
    assert checked.json()["never_signed_in"] is False
    assert [r["grant_type"] for r in servers.authorization.token_requests] == [
        "authorization_code",
        "refresh_token",
    ]


async def test_signing_in_again_keeps_the_plugins_tool_settings(
    client: AsyncClient, servers: SignInServers
) -> None:
    """The same row, the same registered client; only the sign-in is replaced."""
    await sign_in_custom(client, servers)
    await client.put("/plugins/notes/tools/count", json={"enabled": False})
    servers.authorization.expire_access_tokens()
    servers.authorization.refuse_refresh = True
    await client.post("/plugins/notes/check")
    servers.authorization.refuse_refresh = False

    again = await client.post("/plugins/notes/sign-in")
    assert again.status_code == 202, again.text
    page = await approve_in_browser(client, again.json()["authorization_url"])

    assert page.status_code == 200
    plugins = (await client.get("/plugins")).json()
    assert [(p["id"], p["check_failure"]) for p in plugins] == [("notes", None)]
    assert {t["name"]: t["enabled"] for t in plugins[0]["tools"]} == {
        "search": True,
        "count": False,
    }
    assert len(servers.authorization.registered) == 1
    assert servers.protected.authorizations[-1] == "Bearer at-2"


async def test_a_disconnected_oauth_plugin_connects_again_by_signing_in(
    client: AsyncClient, servers: SignInServers
) -> None:
    """Its token went at disconnect, so Connect alone is refused and a sign-in brings it back."""
    await sign_in_custom(client, servers)
    await client.put("/plugins/notes/tools/count", json={"enabled": False})
    disconnected = await client.post("/plugins/notes/disconnect")
    assert disconnected.json()["auth_type"] == "oauth"

    refused = await client.post("/plugins/notes/connect")
    again = await client.post("/plugins/notes/sign-in")
    assert again.status_code == 202, again.text
    page = await approve_in_browser(client, again.json()["authorization_url"])

    assert refused.json()["detail"]["code"] == "plugin_needs_account"
    assert page.status_code == 200
    [plugin] = (await client.get("/plugins")).json()
    assert plugin["disconnected"] is False
    assert {t["name"]: t["enabled"] for t in plugin["tools"]} == {
        "search": True,
        "count": False,
    }


async def test_no_token_reaches_a_log_line_or_a_response(
    client: AsyncClient, servers: SignInServers, caplog: pytest.LogCaptureFixture
) -> None:
    """Every log line at every level, and every answer the screen reads."""
    caplog.set_level(logging.DEBUG)
    sign_in = await start_custom(client, servers)
    await approve_in_browser(client, sign_in["authorization_url"])
    servers.authorization.expire_access_tokens()
    checked = await client.post("/plugins/notes/check")
    answers = [
        str(sign_in),
        checked.text,
        (await client.get("/plugins")).text,
        (await client.get(f"/plugins/sign-ins/{sign_in['id']}")).text,
    ]

    secrets = ["at-1", "rt-1", "at-2", "rt-2"]
    assert not [s for s in secrets if s in caplog.text]
    assert not [s for s in secrets for answer in answers if s in answer]
